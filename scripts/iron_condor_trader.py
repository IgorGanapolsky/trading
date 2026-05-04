#!/usr/bin/env python3
"""
Iron Condor Trader - 80% Win Rate Strategy

Research backing (Dec 2025):
- Iron condors: 75-85% win rate in normal volatility
- Best when IV Percentile > 50% (premium is rich)
- 30-45 DTE: Optimal theta decay
- 15-20 delta wings: High probability of profit

Strategy:
1. Sell OTM put spread (bull put)
2. Sell OTM call spread (bear call)
3. Collect premium from both sides
4. Max profit if price stays between short strikes

Exit Rules:
- Take profit at 50% of max profit
- Close at 7 DTE (avoid gamma risk)
- Close if one side reaches 100% loss

THIS IS THE MONEY MAKER.
"""

import json
import logging
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

from src.core.trading_constants import MAX_POSITIONS as MAX_OPTION_LEGS
from src.core.trading_profiles import get_iron_condor_strategy_config
from src.orchestrator.telemetry import OrchestratorTelemetry
from src.rag.lessons_learned_rag import LessonsLearnedRAG
from src.safety.mandatory_trade_gate import safe_submit_order
from src.safety.trade_lock import TradeLockTimeout, acquire_trade_lock
from src.safety.trading_halt import get_trading_halt_state
from src.utils.error_monitoring import init_sentry

try:
    load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=False)
except (AssertionError, Exception):
    pass  # In CI, env vars are set via workflow secrets
init_sentry()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
SYSTEM_STATE_PATH = PROJECT_ROOT / "data" / "system_state.json"
IC_ENTRIES_PATH = PROJECT_ROOT / "data" / "ic_entries.json"
MAX_SYNC_STALENESS_HOURS = 18


def select_strikes_by_delta(*args, **kwargs):
    """Compatibility seam for trader tests and callers patching this module."""
    from src.markets.option_chain import (
        select_strikes_by_delta as select_strikes_by_delta_impl,
    )

    return select_strikes_by_delta_impl(*args, **kwargs)


@dataclass
class IronCondorLegs:
    """Iron condor position legs."""

    underlying: str
    expiry: str
    dte: int
    # Put spread (bull put)
    short_put: float
    long_put: float
    # Call spread (bear call)
    short_call: float
    long_call: float
    # Premiums
    credit_received: float
    max_risk: float
    max_profit: float


class IronCondorStrategy:
    """
    Iron Condor implementation.

    This is THE strategy for consistent income:
    - High win rate (75-85%)
    - Defined risk
    - Works in sideways markets
    - Theta decay works for you
    """

    def __init__(self, underlying: str | None = None):
        self.config = get_iron_condor_strategy_config(underlying=underlying)
        self.config["max_positions"] = max(
            self.config["max_positions"],
            max(1, int(MAX_OPTION_LEGS) // 4),
        )
        self._last_strike_selection = None

    @staticmethod
    def _parse_iso_datetime(raw: object) -> datetime | None:
        if raw is None:
            return None
        text = str(raw).strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def _build_trade_signature(self, ic: IronCondorLegs) -> str:
        return (
            f"{ic.underlying}_{ic.expiry}_"
            f"P{int(ic.long_put) if float(ic.long_put).is_integer() else ic.long_put}"
            f"-{int(ic.short_put) if float(ic.short_put).is_integer() else ic.short_put}_"
            f"C{int(ic.short_call) if float(ic.short_call).is_integer() else ic.short_call}"
            f"-{int(ic.long_call) if float(ic.long_call).is_integer() else ic.long_call}"
        )

    def _validate_sync_freshness(self) -> tuple[bool, str, dict]:
        if not SYSTEM_STATE_PATH.exists():
            return False, "system_state.json missing", {"path": str(SYSTEM_STATE_PATH)}
        try:
            state = json.loads(SYSTEM_STATE_PATH.read_text(encoding="utf-8"))
        except Exception as exc:
            return (
                False,
                f"Could not read system_state.json: {exc}",
                {"path": str(SYSTEM_STATE_PATH)},
            )

        sync_health = state.get("sync_health") if isinstance(state, dict) else {}
        if not isinstance(sync_health, dict):
            sync_health = {}
        last_sync_raw = sync_health.get("last_successful_sync")
        sync_time = self._parse_iso_datetime(last_sync_raw)
        if sync_time is None:
            return (
                False,
                "sync_health.last_successful_sync missing or invalid",
                {
                    "path": str(SYSTEM_STATE_PATH),
                    "last_successful_sync": last_sync_raw,
                },
            )

        now_utc = datetime.now(timezone.utc)
        age_hours = round((now_utc - sync_time).total_seconds() / 3600, 2)
        details = {
            "path": str(SYSTEM_STATE_PATH),
            "last_successful_sync": sync_time.isoformat(),
            "age_hours": age_hours,
            "max_age_hours": MAX_SYNC_STALENESS_HOURS,
        }
        if age_hours > MAX_SYNC_STALENESS_HOURS:
            return (
                False,
                f"Broker sync stale: last successful sync was {age_hours:.1f}h ago",
                details,
            )
        return True, "", details

    def _persist_entry_metadata(
        self,
        ic: IronCondorLegs,
        *,
        order_id: str,
        quantity: int,
        entry_reason: str,
    ) -> None:
        selection = getattr(self, "_last_strike_selection", None)
        entry_timestamp = datetime.now(timezone.utc).isoformat()
        entry_key = f"IC_{ic.expiry.replace('-', '')[2:]}"
        ic_entries: dict = {}
        if IC_ENTRIES_PATH.exists():
            try:
                ic_entries = json.loads(IC_ENTRIES_PATH.read_text(encoding="utf-8"))
            except Exception:
                ic_entries = {}

        ic_entries[entry_key] = {
            "credit": ic.credit_received,
            "date": entry_timestamp,
            "entry_time": entry_timestamp,
            "order_id": order_id,
            "underlying": ic.underlying,
            "expiry": ic.expiry,
            "signature": self._build_trade_signature(ic),
            "quantity": quantity,
            "profile_name": self.config.get("name"),
            "validation_phase": True,
            "entry_reason": entry_reason,
            "target_delta": self.config.get("short_delta"),
            "selection_method": getattr(selection, "method", "unknown"),
            "strike_selection_method": getattr(selection, "method", "unknown"),
            "put_delta": getattr(selection, "put_delta", None),
            "call_delta": getattr(selection, "call_delta", None),
            "strikes": {
                "short_put": ic.short_put,
                "short_call": ic.short_call,
                "long_put": ic.long_put,
                "long_call": ic.long_call,
            },
        }
        IC_ENTRIES_PATH.parent.mkdir(parents=True, exist_ok=True)
        IC_ENTRIES_PATH.write_text(json.dumps(ic_entries, indent=2) + "\n", encoding="utf-8")

    def get_underlying_price(self) -> float:
        """Get current price of the configured underlying from Alpaca."""
        # FIX Jan 20, 2026: Fetch real price from Alpaca instead of hardcoding
        # ROOT CAUSE: Hardcoded $595 was causing wrong strike calculations
        # SPY was actually ~$600, causing PUT-only fills (CALL strikes too low)
        try:
            from alpaca.data.historical import StockHistoricalDataClient
            from alpaca.data.requests import StockLatestQuoteRequest

            from src.utils.alpaca_client import get_alpaca_credentials

            api_key, secret = get_alpaca_credentials()
            if api_key and secret:
                data_client = StockHistoricalDataClient(api_key, secret)
                underlying = self.config["underlying"]
                request = StockLatestQuoteRequest(symbol_or_symbols=[underlying])
                quote = data_client.get_stock_latest_quote(request)
                if underlying in quote:
                    mid_price = (quote[underlying].ask_price + quote[underlying].bid_price) / 2
                    logger.info(f"Live {underlying} price from Alpaca: ${mid_price:.2f}")
                    return mid_price
        except Exception as e:
            logger.warning(f"Could not fetch live {self.config['underlying']} price: {e}")

        # FIXED Mar 23, 2026: No fallback price. Hardcoded $688 caused wrong
        # strike calculations when SPY moved. Trading on stale prices = losses.
        raise RuntimeError(
            f"Live {self.config['underlying']} price unavailable — refusing to trade on stale data"
        )

    def calculate_strikes(self, price: float) -> tuple[float, float, float, float]:
        """
        Calculate iron condor strikes using live delta from Alpaca option chain.

        Falls back to 5% OTM heuristic if chain data is unavailable.
        Stores the selection result on self._last_strike_selection for tracing.
        """
        selection = select_strikes_by_delta(
            underlying=self.config["underlying"],
            underlying_price=price,
            wing_width=self.config["wing_width"],
            target_delta=self.config["short_delta"],
            target_dte=self.config["target_dte"],
            min_dte=self.config["min_dte"],
            max_dte=self.config["max_dte"],
        )

        self._last_strike_selection = selection

        if selection.method == "live_delta":
            logger.info(
                f"LIVE DELTA strikes: put delta={selection.put_delta:.3f}, "
                f"call delta={selection.call_delta:.3f}"
            )
        else:
            logger.error(
                "BLOCKED: Heuristic fallback has unknown delta (0.0). "
                "Cannot verify 15-20 delta mandate. Refusing to trade."
            )
            return None, None, None, None

        return selection.long_put, selection.short_put, selection.short_call, selection.long_call

    def calculate_premiums(self, legs: tuple[float, float, float, float], dte: int) -> dict:
        """
        Estimate premiums for iron condor legs.

        FIXED Mar 23, 2026: Estimates only used for pre-trade sizing check.
        Actual execution uses live bid/ask from Alpaca option chain.
        The MLEG order gets market fill — these estimates just gate whether
        the trade is worth attempting.
        """
        wing_width = self.config["wing_width"]

        # Use live bids from chain if available
        selection = getattr(self, "_last_strike_selection", None)
        if selection and selection.method == "live_delta" and selection.put_bid > 0:
            estimated_credit = round(selection.net_credit, 2)
            logger.info(
                f"Live net credit: ${estimated_credit:.2f} "
                f"(short put ${selection.put_bid:.2f} + short call ${selection.call_bid:.2f} "
                f"- long put ${selection.long_put_ask:.2f} - long call ${selection.long_call_ask:.2f})"
            )
        else:
            # Conservative fallback for a $10-wide index ETF condor when live quotes are unavailable.
            estimated_credit = 1.50
        max_risk = (wing_width * 100) - (estimated_credit * 100)

        return {
            "credit": estimated_credit,
            "max_risk": max_risk,
            "max_profit": estimated_credit * 100,
            "risk_reward": max_risk / (estimated_credit * 100) if estimated_credit > 0 else 0,
        }

    def find_trade(self) -> Optional[IronCondorLegs]:
        """
        Find an iron condor trade matching our criteria.
        """
        price = self.get_underlying_price()
        logger.info(f"Underlying price: ${price:.2f}")

        # Calculate strikes (returns None tuple if delta unavailable)
        long_put, short_put, short_call, long_call = self.calculate_strikes(price)
        if long_put is None:
            logger.error("No valid strikes found (delta unavailable). Aborting trade.")
            return None
        logger.info(f"Strikes: LP={long_put} SP={short_put} SC={short_call} LC={long_call}")

        selection = getattr(self, "_last_strike_selection", None)
        if selection and getattr(selection, "expiry", None):
            expiry_date = datetime.strptime(selection.expiry, "%Y-%m-%d")
            days_until_friday = (4 - expiry_date.weekday()) % 7
            expiry_date += timedelta(days=days_until_friday)
        else:
            target_date = datetime.now() + timedelta(days=self.config["target_dte"])
            days_until_friday = (4 - target_date.weekday()) % 7
            expiry_date = target_date + timedelta(days=days_until_friday)
            if (expiry_date - datetime.now()).days < self.config["min_dte"]:
                expiry_date += timedelta(days=7)
        actual_dte = (expiry_date - datetime.now()).days
        if actual_dte < self.config["min_dte"]:
            expiry_date += timedelta(days=7)
            actual_dte = (expiry_date - datetime.now()).days
        logger.info(
            f"Expiry: {expiry_date.strftime('%Y-%m-%d')} ({expiry_date.strftime('%A')}) - {actual_dte} DTE"
        )

        # Estimate premiums
        premiums = self.calculate_premiums(
            (long_put, short_put, short_call, long_call), self.config["target_dte"]
        )

        # GUARD: Never enter a net-debit iron condor (Phil Town Rule #1)
        if premiums["credit"] <= 0:
            logger.error(
                f"BLOCKED: Net-debit IC (credit=${premiums['credit']:.2f}). "
                f"This would lose money from the start."
            )
            return None

        # GUARD: Minimum credit threshold ($0.50 per IC)
        min_credit = 0.50
        if premiums["credit"] < min_credit:
            logger.warning(
                f"BLOCKED: Credit ${premiums['credit']:.2f} < ${min_credit:.2f} minimum. "
                f"Not enough premium to justify the risk."
            )
            return None

        return IronCondorLegs(
            underlying=self.config["underlying"],
            expiry=expiry_date.strftime("%Y-%m-%d"),
            dte=actual_dte,
            short_put=short_put,
            long_put=long_put,
            short_call=short_call,
            long_call=long_call,
            credit_received=premiums["credit"],
            max_risk=premiums["max_risk"],
            max_profit=premiums["max_profit"],
        )

    def check_entry_conditions(self) -> tuple[bool, str]:
        """
        Check if conditions are right for entry.

        Per LL-269 research (Jan 21, 2026):
        1. VIX 15-25: Ideal - premiums decent, risk manageable
        2. VIX < 15: AVOID - premiums too thin
        3. VIX > 25: CAUTION - volatility too high

        Enhanced with VIX Mean Reversion Signal (LL-296, Jan 22, 2026):
        - Optimal entry when VIX drops FROM a spike (premium still rich)
        - Uses 3-day MA and 2 std dev threshold for signal quality
        """
        from src.constants.trading_thresholds import RiskThresholds

        # LL-296: Try VIX Mean Reversion Signal first (enhanced entry timing)
        try:
            from src.signals.vix_mean_reversion_signal import VIXMeanReversionSignal

            vix_signal = VIXMeanReversionSignal()
            signal = vix_signal.calculate_signal()

            logger.info("=" * 50)
            logger.info("VIX MEAN REVERSION SIGNAL (LL-296)")
            logger.info("=" * 50)
            logger.info(f"Signal: {signal.signal} (confidence: {signal.confidence:.2f})")
            logger.info(f"Current VIX: {signal.current_vix:.2f}")
            logger.info(f"3-day MA: {signal.vix_3day_ma:.2f}")
            logger.info(f"Recent High: {signal.recent_high:.2f}")
            logger.info(f"Reason: {signal.reason}")
            logger.info("=" * 50)

            if signal.signal == "OPTIMAL_ENTRY":
                logger.info("OPTIMAL ENTRY - VIX dropped from spike!")
                return True, f"OPTIMAL: {signal.reason}"

            if signal.signal == "GOOD_ENTRY":
                logger.info("GOOD ENTRY - VIX in favorable range")
                return True, f"GOOD: {signal.reason}"

            if signal.signal == "AVOID":
                logger.warning(f"BLOCKED by VIX signal: {signal.reason}")
                return False, signal.reason

            # NEUTRAL: Fall through to legacy check for additional validation
            logger.info("NEUTRAL signal - running legacy VIX check")

        except Exception as e:
            logger.warning(f"VIX Mean Reversion Signal failed: {e} - using legacy check")

        # Legacy VIX check (fallback)
        try:
            from src.options.vix_monitor import VIXMonitor

            vix_monitor = VIXMonitor()
            current_vix = vix_monitor.get_current_vix()

            logger.info(f"Legacy VIX Check: Current VIX = {current_vix:.2f}")

            # Check VIX is in optimal range (15-25 per LL-269)
            if current_vix < RiskThresholds.VIX_OPTIMAL_MIN:
                reason = (
                    f"VIX {current_vix:.2f} < {RiskThresholds.VIX_OPTIMAL_MIN} (premiums too thin)"
                )
                logger.warning(f"BLOCKED: {reason}")
                return False, reason

            if current_vix > RiskThresholds.VIX_HALT_THRESHOLD:
                reason = f"VIX {current_vix:.2f} > {RiskThresholds.VIX_HALT_THRESHOLD} (volatility too extreme)"
                logger.warning(f"BLOCKED: {reason}")
                return False, reason

            if current_vix > RiskThresholds.VIX_OPTIMAL_MAX:
                # Between 25-30: Allow with caution
                logger.warning(
                    f"CAUTION: VIX {current_vix:.2f} > {RiskThresholds.VIX_OPTIMAL_MAX} (elevated volatility)"
                )
                logger.warning("   Consider wider strikes or smaller position size")
                return True, f"VIX {current_vix:.2f} elevated but acceptable"

            # VIX in optimal range (15-25)
            logger.info(f"VIX {current_vix:.2f} is in optimal range (15-25)")
            return True, f"VIX {current_vix:.2f} favorable"

        except Exception as e:
            # FIXED Mar 23, 2026: If VIX check fails, BLOCK the trade.
            # Previous behavior: allowed trade on VIX failure, which let trades
            # through during VIX > 30 (tariff crash March 2026).
            logger.error(f"VIX check failed: {e} - BLOCKING trade (fail-safe)")
            return False, f"VIX check failed: {e} — refusing to trade blind"

    def check_iv_vs_rv(self) -> tuple[bool, str]:
        """Check if implied volatility exceeds realized volatility.

        We only sell premium when IV > RV (market pricing in more risk than
        realized). Soft gate: allows trade if data unavailable.
        """
        try:
            from src.data.iv_data_provider import IVDataProvider

            provider = IVDataProvider()
            underlying = self.config["underlying"]
            current_iv = provider.get_current_iv(underlying)
            rv = self._compute_realized_vol()

            if rv is None or rv <= 0:
                logger.warning("Could not compute realized vol — allowing trade (soft gate)")
                return True, "RV unavailable — IV check skipped"

            iv_rv_ratio = current_iv / rv if rv > 0 else 999.0

            logger.info("=" * 50)
            logger.info("IV vs RV PREMIUM CHECK")
            logger.info("=" * 50)
            logger.info(f"  {underlying} IV (annualized): {current_iv:.1%}")
            logger.info(f"  {underlying} 20d RV:          {rv:.1%}")
            logger.info(f"  IV/RV ratio:         {iv_rv_ratio:.2f}")
            logger.info("=" * 50)

            if iv_rv_ratio < 0.90:
                reason = (
                    f"IV ({current_iv:.1%}) < RV ({rv:.1%}), ratio={iv_rv_ratio:.2f} — "
                    f"premium too cheap to sell"
                )
                logger.warning(f"BLOCKED: {reason}")
                return False, reason

            logger.info(f"IV/RV={iv_rv_ratio:.2f} — premium is rich, good to sell")
            return True, f"IV/RV={iv_rv_ratio:.2f} favorable"

        except Exception as e:
            logger.warning(f"IV/RV check failed ({e}) — allowing trade (soft gate)")
            return True, f"IV/RV check unavailable: {e}"

    def _compute_realized_vol(self, lookback_days: int = 20) -> float | None:
        """Compute annualized realized volatility from underlying daily closes."""
        try:
            import numpy as np
            from alpaca.data.historical import StockHistoricalDataClient
            from alpaca.data.requests import StockBarsRequest
            from alpaca.data.timeframe import TimeFrame

            from src.utils.alpaca_client import get_alpaca_credentials

            api_key, secret = get_alpaca_credentials()
            if not api_key or not secret:
                return None

            client = StockHistoricalDataClient(api_key, secret)
            underlying = self.config["underlying"]
            request = StockBarsRequest(
                symbol_or_symbols=underlying,
                timeframe=TimeFrame.Day,
                start=datetime.now() - timedelta(days=lookback_days + 10),
                end=datetime.now(),
            )
            bars = client.get_stock_bars(request)

            if underlying not in bars.data or len(bars.data[underlying]) < lookback_days:
                return None

            closes = [float(bar.close) for bar in bars.data[underlying]]
            if len(closes) < 2:
                return None

            returns = np.diff(np.log(closes))
            rv = float(np.std(returns[-lookback_days:]) * np.sqrt(252))
            return rv

        except Exception as e:
            logger.warning(f"Failed to compute realized vol: {e}")
            return None

    def _build_decision_trace(self, ic: IronCondorLegs, entry_reason: str) -> dict:
        """Build a decision trace capturing market context at entry time (Context Graph pattern)."""
        trace: dict = {
            "captured_at": datetime.now().isoformat(),
            "entry_reason": entry_reason,
            "market_context": {},
            "signals_checked": [],
            "strike_selection": {
                "method": getattr(
                    getattr(self, "_last_strike_selection", None), "method", "unknown"
                ),
                "short_put": ic.short_put,
                "short_call": ic.short_call,
                "put_delta": getattr(
                    getattr(self, "_last_strike_selection", None), "put_delta", 0.0
                ),
                "call_delta": getattr(
                    getattr(self, "_last_strike_selection", None), "call_delta", 0.0
                ),
                "wing_width": ic.long_call - ic.short_call,
            },
            "precedent_query": f"{ic.underlying} iron_condor {ic.dte}DTE",
        }
        try:
            from src.signals.vix_mean_reversion_signal import VIXMeanReversionSignal

            sig = VIXMeanReversionSignal()
            signal = sig.calculate_signal()
            trace["market_context"]["vix"] = signal.current_vix
            trace["market_context"]["vix_3day_ma"] = signal.vix_3day_ma
            trace["signals_checked"].append("vix_mean_reversion")
        except Exception:
            pass
        try:
            from src.data.iv_data_provider import IVDataProvider

            iv = IVDataProvider()
            iv_data = iv.get_iv_rank(ic.underlying)
            if iv_data:
                trace["market_context"]["iv_rank"] = iv_data.get("iv_rank")
                trace["signals_checked"].append("iv_rank")
        except Exception:
            pass
        return trace

    def execute(self, ic: IronCondorLegs, live: bool = False, entry_reason: str = "") -> dict:
        """
        Execute the iron condor trade.

        Args:
            ic: Iron condor legs to execute
            live: If True, execute on Alpaca. If False, simulate only.
            entry_reason: Why this trade was entered (for decision trace).
        """
        # POSITION CHECK FIRST - Prevent race conditions from parallel workflow runs
        # FIX Jan 22, 2026: Move position check to VERY START before any other logic
        # ROOT CAUSE: Multiple workflow runs could race past position check if it ran late
        if live:
            sync_ok, sync_reason, sync_details = self._validate_sync_freshness()
            if not sync_ok:
                logger.error("=" * 60)
                logger.error("SYNC FRESHNESS BLOCKING NEW TRADE")
                logger.error("=" * 60)
                logger.error(sync_reason)
                logger.error(sync_details)
                logger.error("=" * 60)
                return {
                    "timestamp": datetime.now().isoformat(),
                    "strategy": "iron_condor",
                    "underlying": ic.underlying,
                    "status": "BLOCKED_STALE_SYNC",
                    "reason": sync_reason,
                    "sync_health": sync_details,
                }
            logger.info("=" * 60)
            logger.info("POSITION CHECK (MANDATORY FIRST STEP)")
            logger.info("=" * 60)
            try:
                from alpaca.trading.client import TradingClient

                from src.utils.alpaca_client import get_alpaca_credentials

                api_key, secret = get_alpaca_credentials()
                if api_key and secret:
                    client = TradingClient(api_key, secret, paper=True)
                    positions = client.get_all_positions()

                    underlying = ic.underlying
                    # Count option legs for the configured underlying only.
                    spy_option_positions = [
                        p
                        for p in positions
                        if p.symbol.startswith(underlying)
                        and len(p.symbol) > 5  # Options have longer symbols
                    ]

                    # Count TOTAL CONTRACTS
                    total_contracts = sum(abs(int(float(p.qty))) for p in spy_option_positions)
                    unique_symbols = len(spy_option_positions)

                    logger.info(
                        f"Current {underlying} OPTION positions: {unique_symbols} symbols, {total_contracts} contracts"
                    )

                    # Check iron condor count against max_positions config
                    # 1 iron condor = 4 legs (long put, short put, short call, long call)
                    max_ic = int(
                        self.config.get("max_positions", max(1, int(MAX_OPTION_LEGS) // 4))
                    )
                    max_contracts = max_ic * 4
                    current_ic_count = total_contracts // 4

                    if total_contracts >= max_contracts:
                        logger.warning("=" * 60)
                        logger.warning("POSITION LIMIT BLOCKING NEW TRADE")
                        logger.warning("=" * 60)
                        logger.warning(
                            f"REASON: Already have {current_ic_count} iron condor(s) ({total_contracts} contracts, max: {max_ic} ICs / {max_contracts} contracts)"
                        )
                        logger.warning("ACTION: Manage existing positions before opening new ones")
                        logger.warning("POSITIONS:")

                        # Log position details for debugging
                        for p in spy_option_positions:
                            logger.warning(
                                f"   - {p.symbol}: {p.qty} contracts @ ${float(p.avg_entry_price):.2f}"
                            )

                        logger.warning("=" * 60)

                        return {
                            "timestamp": datetime.now().isoformat(),
                            "strategy": "iron_condor",
                            "underlying": ic.underlying,
                            "status": "SKIPPED_POSITION_LIMIT",
                            "reason": f"Already have {current_ic_count}/{max_ic} iron condors ({total_contracts} contracts)",
                            "existing_positions": [
                                {"symbol": p.symbol, "qty": p.qty} for p in spy_option_positions
                            ],
                        }
                    else:
                        logger.info(
                            f"Position check OK: {current_ic_count}/{max_ic} iron condors - room for new entry"
                        )

                    # ADDED Mar 23, 2026: Check for duplicate expiry
                    # Prevents opening a new IC at the same expiry as an existing position
                    target_expiry = ic.expiry.replace("-", "")[2:]  # "2026-04-25" -> "260425"
                    existing_expiries = set()
                    for p in spy_option_positions:
                        if len(p.symbol) > 10:
                            existing_expiries.add(p.symbol[3:9])

                    if target_expiry in existing_expiries:
                        logger.warning(f"BLOCKED: Already have positions at expiry {ic.expiry}")
                        return {
                            "timestamp": datetime.now().isoformat(),
                            "strategy": "iron_condor",
                            "underlying": ic.underlying,
                            "status": "BLOCKED_DUPLICATE_EXPIRY",
                            "reason": f"Already holding legs at expiry {ic.expiry}",
                        }
            except Exception as pos_err:
                # CRITICAL: If we can't verify positions, BLOCK the trade
                # This prevents placing duplicate trades when Alpaca API fails
                logger.error("=" * 60)
                logger.error("POSITION CHECK FAILED - BLOCKING TRADE")
                logger.error("=" * 60)
                logger.error(f"ERROR: {pos_err}")
                logger.error("REASON: Cannot verify current positions")
                logger.error("ACTION: Trade blocked to prevent position accumulation")
                logger.error("=" * 60)
                return {
                    "timestamp": datetime.now().isoformat(),
                    "strategy": "iron_condor",
                    "underlying": ic.underlying,
                    "status": "BLOCKED_POSITION_CHECK_FAILED",
                    "reason": f"Position check failed: {pos_err}",
                }

        # Query RAG for lessons before trading
        logger.info("Checking RAG lessons before execution...")
        rag = LessonsLearnedRAG()

        # Check for strategy-specific failures
        # FIX Mar 23, 2026: Only block on ACTIVE INCIDENT lessons, not research.
        # Research lessons (LL-268, LL-277) were blocking ALL trades because
        # the RAG index had stale severity=CRITICAL. Research lessons inform
        # strategy but should not block execution.
        strategy_lessons = rag.search("iron condor failures losses", top_k=3)
        for lesson, score in strategy_lessons:
            snippet_lower = lesson.snippet.lower()
            title_lower = lesson.title.lower()
            if (
                lesson.severity == "RESOLVED"
                or "resolved" in snippet_lower
                or "fixed" in snippet_lower
            ):
                logger.info(f"Skipping resolved/fixed lesson: {lesson.id}")
                continue
            # Skip research/optimization lessons — they inform, not block
            if "research" in title_lower or "optimization" in title_lower:
                logger.info(f"Skipping research lesson: {lesson.id}")
                continue
            # Skip known-fixed lessons whose RAG index is stale
            # LL-279 (partial auto-close) fixed Jan 2026, LL-268/277 are research
            if any(fixed_id in lesson.id for fixed_id in ["LL-279", "LL-268", "LL-277"]):
                logger.info(f"Skipping known-fixed lesson: {lesson.id}")
                continue
            if lesson.severity == "CRITICAL" and "iron condor" in lesson.title.lower():
                logger.error(f"BLOCKED by RAG: {lesson.title} (severity: {lesson.severity})")
                logger.error(f"Prevention: {lesson.prevention}")
                return {
                    "timestamp": datetime.now().isoformat(),
                    "strategy": "iron_condor",
                    "status": "BLOCKED_BY_RAG",
                    "reason": f"Critical lesson: {lesson.title}",
                    "lesson_id": lesson.id,
                }

        # Check for ticker-specific failures
        ticker_lessons = rag.search(f"{ic.underlying} trading failures options losses", top_k=3)
        for lesson, score in ticker_lessons:
            # Skip lessons that have been resolved or fixed
            if lesson.severity == "RESOLVED" or "resolved" in lesson.snippet.lower():
                logger.info(f"Skipping resolved lesson: {lesson.id}")
                continue
            # Only block on unresolved CRITICAL lessons about this ticker's execution
            if lesson.severity == "CRITICAL" and ic.underlying.lower() in lesson.title.lower():
                logger.error(f"BLOCKED by RAG: {lesson.title} (severity: {lesson.severity})")
                logger.error(f"Prevention: {lesson.prevention}")
                return {
                    "timestamp": datetime.now().isoformat(),
                    "strategy": "iron_condor",
                    "underlying": ic.underlying,
                    "status": "BLOCKED_BY_RAG",
                    "reason": f"Critical lesson for {ic.underlying}: {lesson.title}",
                    "lesson_id": lesson.id,
                }

        logger.info("RAG checks passed - proceeding with execution")

        if live:
            try:
                from src.safety.behavioral_guard import BehavioralGuard

                guard_result = BehavioralGuard.evaluate(
                    ic.underlying,
                    expiry=ic.expiry,
                    spy_change_pct=None,
                )
                if not guard_result.passed:
                    reason = "; ".join(guard_result.rejections) or "behavioral guard rejection"
                    logger.warning("BLOCKED by behavioral guard: %s", reason)
                    return {
                        "timestamp": datetime.now().isoformat(),
                        "strategy": "iron_condor",
                        "underlying": ic.underlying,
                        "status": "BLOCKED_BEHAVIORAL_GUARD",
                        "reason": reason,
                        "checks_run": guard_result.checks_run,
                        "warnings": guard_result.warnings,
                    }
            except Exception as guard_err:
                logger.warning(f"Behavioral guard check skipped due to error: {guard_err}")

        logger.info("=" * 60)
        logger.info("EXECUTING IRON CONDOR" + (" (LIVE)" if live else " (SIMULATED)"))
        logger.info("=" * 60)
        logger.info(f"Underlying: {ic.underlying}")
        logger.info(f"Expiry: {ic.expiry} ({ic.dte} DTE)")
        logger.info(f"Put Spread: {ic.long_put}/{ic.short_put}")
        logger.info(f"Call Spread: {ic.short_call}/{ic.long_call}")
        logger.info(f"Credit: ${ic.credit_received:.2f} per share")
        logger.info(f"Max Profit: ${ic.max_profit:.2f}")
        logger.info(f"Max Risk: ${ic.max_risk:.2f}")
        logger.info("=" * 60)

        status = "SIMULATED"
        order_ids = []

        # DEBUG: Log execution mode (Jan 23, 2026 - trace SIMULATED issue)
        logger.info("=" * 60)
        logger.info(f"EXECUTION MODE DEBUG: live={live}")
        logger.info("=" * 60)

        # LIVE EXECUTION - Dec 29, 2025 fix
        if live:
            logger.info("Entering LIVE execution block...")
            try:
                from alpaca.trading.client import TradingClient
                from alpaca.trading.enums import OrderClass, OrderSide
                from alpaca.trading.requests import OptionLegRequest

                from src.utils.alpaca_client import get_alpaca_credentials

                api_key, secret = get_alpaca_credentials()

                # DEBUG: Log credential status
                logger.info(
                    f"Credentials check: api_key={'SET' if api_key else 'NONE'}, secret={'SET' if secret else 'NONE'}"
                )
                if api_key:
                    logger.info(f"  api_key length: {len(api_key)}, starts with: {api_key[:4]}...")

                if api_key and secret:
                    client = TradingClient(api_key, secret, paper=True)

                    # Build option symbols (OCC format: SPY251229P00580000)
                    exp_formatted = ic.expiry.replace("-", "")[2:]  # YYMMDD

                    def build_occ(strike: float, opt_type: str) -> str:
                        strike_str = f"{int(strike * 1000):08d}"
                        return f"{ic.underlying}{exp_formatted}{opt_type}{strike_str}"

                    long_put_sym = build_occ(ic.long_put, "P")
                    short_put_sym = build_occ(ic.short_put, "P")
                    short_call_sym = build_occ(ic.short_call, "C")
                    long_call_sym = build_occ(ic.long_call, "C")

                    logger.info(f"Option symbols: LP={long_put_sym}, SP={short_put_sym}")
                    logger.info(f"                SC={short_call_sym}, LC={long_call_sym}")

                    # FIX Jan 26, 2026: Use MLeg (multi-leg) orders to ensure all 4 legs
                    # fill together or not at all. This prevents partial fills that cause losses.
                    # Previous approach of submitting legs separately caused short legs to be
                    # rejected as "uncovered" before long (protective) legs filled.

                    # Build OptionLegRequest for each leg of the iron condor
                    option_legs = [
                        OptionLegRequest(symbol=long_put_sym, side=OrderSide.BUY, ratio_qty=1),
                        OptionLegRequest(symbol=short_put_sym, side=OrderSide.SELL, ratio_qty=1),
                        OptionLegRequest(symbol=short_call_sym, side=OrderSide.SELL, ratio_qty=1),
                        OptionLegRequest(symbol=long_call_sym, side=OrderSide.BUY, ratio_qty=1),
                    ]

                    # Validation phase: size at one contract until expectancy is proven.
                    from src.core.trading_constants import MAX_CONTRACTS_PER_TRADE

                    ic_qty = MAX_CONTRACTS_PER_TRADE

                    logger.info(f"📋 Building MLeg iron condor order ({ic_qty} contracts)...")
                    logger.info(f"   Long Put:   {long_put_sym} (BUY x{ic_qty})")
                    logger.info(f"   Short Put:  {short_put_sym} (SELL x{ic_qty})")
                    logger.info(f"   Short Call: {short_call_sym} (SELL x{ic_qty})")
                    logger.info(f"   Long Call:  {long_call_sym} (BUY x{ic_qty})")

                    # Use LIMIT order to control entry credit (market orders lose $12-40/trade in slippage)
                    # The executor supports LimitOrderRequest with net_credit as limit_price.
                    # Alpaca MLEG limit: negative limit_price = minimum credit we'll accept.
                    try:
                        from alpaca.trading.enums import TimeInForce
                        from alpaca.trading.requests import LimitOrderRequest

                        # Calculate limit price: use estimated credit with $0.05 concession
                        limit_credit = round(ic.credit_received - 0.05, 2)
                        if limit_credit < 0.50:
                            limit_credit = 0.50  # Floor: never accept less than $0.50
                        logger.info(f"   Limit price: -${limit_credit:.2f} (credit per contract)")
                        logger.info(f"   Total credit target: ~${limit_credit * ic_qty * 100:.0f}")

                        order_req = LimitOrderRequest(
                            qty=ic_qty,
                            order_class=OrderClass.MLEG,
                            legs=option_legs,
                            time_in_force=TimeInForce.DAY,
                            limit_price=round(-limit_credit, 2),  # Negative = credit
                        )

                        logger.info("🚀 Submitting MLeg iron condor order...")
                        order = safe_submit_order(client, order_req)

                        order_ids.append(
                            {
                                "order_id": str(order.id),
                                "type": "mleg_iron_condor",
                                "legs": [
                                    long_put_sym,
                                    short_put_sym,
                                    short_call_sym,
                                    long_call_sym,
                                ],
                            }
                        )

                        logger.info(f"✅ MLeg order submitted: {order.id}")
                        logger.info(f"   Status: {order.status}")
                        status = "LIVE_SUBMITTED"

                        # FIX Apr 3, 2026: Place GTC 50% profit close order AFTER fill.
                        # Data shows 90% of trades closed by manage script in < 1 hour
                        # at 6.5% win rate. A GTC limit order on Alpaca lets theta work.
                        # SAFETY: Must wait for entry fill — placing a close order before
                        # the entry fills would create naked positions in the opposite direction.
                        try:
                            profit_target_credit = round(
                                limit_credit * self.config["take_profit_pct"],
                                2,
                            )
                            close_debit = round(limit_credit - profit_target_credit, 2)

                            # Poll for entry fill (max 60 seconds)
                            entry_filled = False
                            for _poll in range(12):
                                refreshed = client.get_order_by_id(order.id)
                                if str(refreshed.status) in ("OrderStatus.FILLED", "filled"):
                                    entry_filled = True
                                    logger.info(
                                        f"   Entry order FILLED at {refreshed.filled_avg_price}"
                                    )
                                    break
                                if str(refreshed.status) in (
                                    "OrderStatus.CANCELED",
                                    "OrderStatus.EXPIRED",
                                    "OrderStatus.REJECTED",
                                    "canceled",
                                    "expired",
                                    "rejected",
                                ):
                                    logger.warning(
                                        f"   Entry order {refreshed.status} — skipping close order"
                                    )
                                    break
                                time.sleep(5)

                            if entry_filled:
                                close_legs = [
                                    OptionLegRequest(
                                        symbol=long_put_sym, side=OrderSide.SELL, ratio_qty=1
                                    ),
                                    OptionLegRequest(
                                        symbol=short_put_sym, side=OrderSide.BUY, ratio_qty=1
                                    ),
                                    OptionLegRequest(
                                        symbol=short_call_sym, side=OrderSide.BUY, ratio_qty=1
                                    ),
                                    OptionLegRequest(
                                        symbol=long_call_sym, side=OrderSide.SELL, ratio_qty=1
                                    ),
                                ]

                                close_order_req = LimitOrderRequest(
                                    qty=ic_qty,
                                    order_class=OrderClass.MLEG,
                                    legs=close_legs,
                                    time_in_force=TimeInForce.GTC,
                                    limit_price=round(close_debit, 2),
                                )

                                close_order = safe_submit_order(client, close_order_req)
                                logger.info(
                                    f"✅ GTC 50% profit close order placed: {close_order.id}"
                                )
                                logger.info(
                                    f"   Close at ${close_debit:.2f} debit (50% of ${limit_credit:.2f} credit)"
                                )
                                order_ids.append(
                                    {
                                        "order_id": str(close_order.id),
                                        "type": "gtc_profit_target_close",
                                        "close_debit": str(close_debit),
                                    }
                                )
                            else:
                                logger.warning(
                                    "   Entry not filled within 60s — close order deferred to manage script"
                                )
                        except Exception as close_err:
                            logger.warning(f"⚠️ Could not place GTC profit close: {close_err}")
                            logger.warning(
                                "   Will rely on manage_iron_condor_positions.py for exits"
                            )

                        # Save entry provenance so exits and audits can trace the actual setup.
                        try:
                            self._persist_entry_metadata(
                                ic,
                                order_id=str(order.id),
                                quantity=ic_qty,
                                entry_reason=entry_reason,
                            )
                            logger.info(
                                f"   Saved entry provenance for {self._build_trade_signature(ic)} "
                                f"to {IC_ENTRIES_PATH}"
                            )
                        except Exception as e:
                            logger.warning(f"   Failed to save entry provenance: {e}")

                    except Exception as mleg_error:
                        logger.error(f"❌ MLeg order failed: {mleg_error}")
                        logger.error("   Iron condor NOT placed - no partial fills")
                        status = "LIVE_FAILED"
                else:
                    logger.error("=" * 60)
                    logger.error("CREDENTIAL FAILURE - LIVE EXECUTION BLOCKED")
                    logger.error("=" * 60)
                    logger.error(f"api_key is {'set' if api_key else 'NONE'}")
                    logger.error(f"secret is {'set' if secret else 'NONE'}")
                    logger.error("Check workflow env vars and GitHub secrets!")
                    logger.error("Expected: ALPACA_PAPER_TRADING_5K_API_KEY")
                    logger.error("=" * 60)

            except Exception as e:
                logger.error(f"Live execution error: {e}")
                import traceback

                logger.error(f"Traceback: {traceback.format_exc()}")
                status = "LIVE_ERROR"

        trade = {
            "timestamp": datetime.now().isoformat(),
            "strategy": "iron_condor",
            "underlying": ic.underlying,
            "symbol": ic.underlying,  # Add symbol field for dashboard compatibility
            "expiry": ic.expiry,
            "dte": ic.dte,
            "legs": {
                "long_put": ic.long_put,
                "short_put": ic.short_put,
                "short_call": ic.short_call,
                "long_call": ic.long_call,
            },
            "credit": ic.credit_received,
            "max_profit": ic.max_profit,
            "max_risk": ic.max_risk,
            "status": status,
            "order_ids": order_ids,
            "decision_trace": self._build_decision_trace(ic, entry_reason),
        }

        # Only record successful trades (not failures)
        if status not in ["LIVE_FAILED", "LIVE_ERROR"]:
            self._record_trade(trade)
        else:
            logger.warning(f"Trade NOT recorded due to failure status: {status}")

        return trade

    def _record_trade(self, trade: dict):
        """Record trade for learning."""
        try:
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from src.learning.trade_memory import TradeMemory

            # Record to trade memory
            memory = TradeMemory()
            memory.add_trade(
                {
                    "symbol": trade["underlying"],
                    "strategy": "iron_condor",
                    "entry_reason": "high_iv_environment",
                    "won": None,  # Unknown until closed — do not pollute learning data
                    "pnl": None,  # Set by sync_closed_positions.py on exit
                    "lesson": f"Opened IC at {trade['credit']:.2f} credit, {trade['dte']} DTE",
                }
            )

            # Update Thompson Sampler (this trade is iron_condor strategy)
            # Don't update win/loss yet - only when closed

            logger.info("Trade recorded to memory systems")
        except Exception as e:
            logger.warning(f"Failed to record trade: {e}")

        # Save to file
        trades_file = Path(f"data/trades_{datetime.now().strftime('%Y-%m-%d')}.json")
        trades_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            trades = []
            if trades_file.exists():
                with open(trades_file) as f:
                    trades = json.load(f)
            trades.append(trade)
            with open(trades_file, "w") as f:
                json.dump(trades, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save trade: {e}")


def main():
    """Run iron condor strategy."""
    import argparse

    parser = argparse.ArgumentParser(description="Iron Condor Trader")
    parser.add_argument("--live", action="store_true", help="Execute LIVE trades on Alpaca")
    parser.add_argument("--dry-run", action="store_true", help="Dry run (simulate only)")
    parser.add_argument("--symbol", type=str, default=None, help="Underlying symbol override")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force execution - bypass VIX checks (CEO directive mode)",
    )
    args = parser.parse_args()

    # Default to LIVE mode as of Dec 29, 2025 to hit $100/day target
    live_mode = args.live or (not args.dry_run)

    telemetry = OrchestratorTelemetry()
    strategy = IronCondorStrategy(underlying=args.symbol)
    ticker = strategy.config["underlying"]
    telemetry.start_ticker_decision(ticker)
    session_profile = {
        "session_type": "iron_condor_trader",
        # We don't require market calendar calls; keep field for downstream consumers.
        "is_market_day": None,
    }

    logger.info("IRON CONDOR TRADER - STARTING")
    logger.info(f"Mode: {'LIVE' if live_mode else 'SIMULATED'}")
    logger.info(f"Symbol: {ticker}")

    try:
        halt_state = get_trading_halt_state()
        if halt_state.active:
            logger.warning("=" * 60)
            logger.warning("TRADING HALTED - execution blocked")
            logger.warning("=" * 60)
            logger.warning(halt_state.reason)
            logger.warning(f"Active halt file: {halt_state.path}")
            logger.warning("=" * 60)
            telemetry.update_ticker_decision(
                ticker,
                gate=0,
                status="REJECT",
                rejection_reason=f"Trading halted - {halt_state.kind}",
                indicators={"halt_file": halt_state.path, "halt_kind": halt_state.kind},
            )
            return {"success": False, "reason": halt_state.reason}

        try:
            # LL-297 FIX (Jan 23, 2026): Daily trade limit to prevent churning
            # ROOT CAUSE: 21 trades in one day caused $11.29 loss from bid/ask spreads
            # SOLUTION: Only 1 iron condor entry per day (4 legs max)
            # NOTE: trades_{date}.json can include Alpaca fill-sync entries (strategy=alpaca_sync).
            # We count *structures* (strategy-level iron condor entries) instead of raw rows.
            try:
                from src.core.trading_constants import (
                    MAX_DAILY_STRUCTURES as MAX_STRUCTURES_PER_DAY,
                )
            except Exception:
                MAX_STRUCTURES_PER_DAY = 1
            trades_file = Path(f"data/trades_{datetime.now().strftime('%Y-%m-%d')}.json")
            if trades_file.exists():
                try:
                    with open(trades_file) as f:
                        today_trades = json.load(f)
                    if not isinstance(today_trades, list):
                        today_trades = []
                    structures_today = len(
                        [
                            t
                            for t in today_trades
                            if isinstance(t, dict)
                            and t.get("strategy") == "iron_condor"
                            and t.get("status") != "SIMULATED"
                            and (t.get("order_ids") or isinstance(t.get("legs"), dict))
                        ]
                    )
                    if structures_today >= MAX_STRUCTURES_PER_DAY:
                        logger.warning("=" * 60)
                        logger.warning("DAILY TRADE LIMIT REACHED - BLOCKING NEW TRADES")
                        logger.warning("=" * 60)
                        logger.warning(
                            f"Structures today: {structures_today} (max: {MAX_STRUCTURES_PER_DAY})"
                        )
                        logger.warning("Reason: Prevent churning and bid/ask spread losses")
                        logger.warning("=" * 60)
                        telemetry.update_ticker_decision(
                            ticker,
                            gate=1,
                            status="REJECT",
                            rejection_reason=(
                                f"Daily structure limit reached: {structures_today}/{MAX_STRUCTURES_PER_DAY}"
                            ),
                            indicators={
                                "structures_today": structures_today,
                                "max_structures_per_day": MAX_STRUCTURES_PER_DAY,
                            },
                        )
                        return {
                            "success": False,
                            "reason": f"Daily structure limit reached: {structures_today}/{MAX_STRUCTURES_PER_DAY}",
                        }
                except Exception as e:
                    logger.warning(f"Could not check daily trades: {e}")
        except Exception as e:
            logger.warning(f"Daily trade limit guard failed: {e}")

        # HARD BLOCK: Validate ticker before proceeding (Jan 20 2026 - SOFI crisis)
        from src.utils.ticker_validator import validate_ticker

        validate_ticker(strategy.config["underlying"], context="iron_condor_trader")

        # Check entry conditions (unless --force bypasses VIX checks)
        if args.force:
            logger.warning("=" * 60)
            logger.warning("🚨 FORCE MODE ENABLED - CEO DIRECTIVE")
            logger.warning("=" * 60)
            logger.warning("Bypassing VIX entry conditions per CEO directive")
            logger.warning("Position check and RAG safety checks still active")
            logger.warning("=" * 60)
            should_enter = True
            reason = "FORCED - CEO directive bypassing VIX checks"
            telemetry.update_ticker_decision(
                ticker,
                gate=1,
                status="PASS",
                indicators={"forced": True, "entry_reason": reason},
            )
        else:
            should_enter, reason = strategy.check_entry_conditions()
            logger.info(f"Entry conditions: {should_enter} ({reason})")
            if should_enter:
                # Secondary gate: IV vs RV premium check
                iv_ok, iv_reason = strategy.check_iv_vs_rv()
                if not iv_ok:
                    should_enter = False
                    reason = iv_reason
                else:
                    reason = f"{reason} | {iv_reason}"

            if should_enter:
                telemetry.update_ticker_decision(
                    ticker,
                    gate=1,
                    status="PASS",
                    indicators={"entry_reason": reason},
                )
            else:
                telemetry.update_ticker_decision(
                    ticker,
                    gate=1,
                    status="REJECT",
                    rejection_reason=reason,
                    indicators={"entry_reason": reason},
                )
                logger.info("Skipping trade - conditions not met")
                return {"success": False, "reason": reason}

        # REGIME GATE: Fail-closed. Unknown regime = no entry.
        try:
            from src.utils.regime_detector import RegimeDetector

            detector = RegimeDetector()
            snapshot = detector.detect_live_regime_with_prediction()
            logger.info(
                f"Regime: {snapshot.label} (id={snapshot.regime_id}, "
                f"confidence={snapshot.confidence:.2f}, VIX={snapshot.vix_level:.1f})"
            )
            if snapshot.regime_id < 0 or snapshot.confidence < 0.3:
                msg = (
                    f"REGIME BLOCKED: unknown/low-confidence "
                    f"(id={snapshot.regime_id}, conf={snapshot.confidence:.2f}). Fail-closed."
                )
                logger.warning(msg)
                telemetry.update_ticker_decision(
                    ticker,
                    gate=2,
                    status="REJECT",
                    rejection_reason=msg,
                    indicators={"regime": "unknown", "regime_id": snapshot.regime_id},
                )
                return {"success": False, "reason": msg}
            if snapshot.regime_id >= 2:  # volatile or spike
                msg = (
                    f"REGIME BLOCKED: {snapshot.label} (id={snapshot.regime_id}). "
                    f"Iron condors require calm/low-trend markets."
                )
                logger.warning(msg)
                telemetry.update_ticker_decision(
                    ticker,
                    gate=2,
                    status="REJECT",
                    rejection_reason=msg,
                    indicators={"regime": snapshot.label, "regime_id": snapshot.regime_id},
                )
                return {"success": False, "reason": msg}
            if hasattr(snapshot, "transition_prediction") and snapshot.transition_prediction:
                tp = snapshot.transition_prediction
                if tp.transition_detected and tp.predicted_regime in ("volatile", "spike"):
                    msg = (
                        f"REGIME TRANSITION: {tp.predicted_regime} predicted "
                        f"(prob={tp.transition_probability:.2f}). Blocking entry."
                    )
                    logger.warning(msg)
                    return {"success": False, "reason": msg}
        except Exception as e:
            msg = f"REGIME BLOCKED: detection failed ({e}). Fail-closed."
            logger.warning(msg)
            return {"success": False, "reason": msg}

        # IV RANK GATE: Only sell premium when IV is rich (IV Rank > 20)
        try:
            from src.data.iv_data_provider import IVDataProvider

            iv_provider = IVDataProvider()
            iv_rank = iv_provider.get_iv_rank("SPY")
            if iv_rank is not None:
                logger.info(f"IV Rank: {iv_rank:.1f}")
                if iv_rank < 20:
                    msg = f"IV Rank {iv_rank:.1f} < 20 — premium too cheap to sell iron condors"
                    logger.warning(msg)
                    telemetry.update_ticker_decision(
                        ticker,
                        gate=2,
                        status="REJECT",
                        rejection_reason=msg,
                        indicators={"iv_rank": iv_rank},
                    )
                    return {"success": False, "reason": msg}
        except Exception as e:
            logger.debug(f"IV Rank check skipped (non-blocking): {e}")

        try:
            # LLM PRE-TRADE RESEARCH AGENT (Feb 2026)
            # DeepSeek-R1 analyzes market conditions and advises on IC entry.
            # Advisory only — hard risk limits are never overridden.
            try:
                from src.llm.trade_opinion import get_trade_opinion
                from src.ml.trade_confidence import get_trade_confidence_model

                # Gather context for the research agent
                tc_model = get_trade_confidence_model()
                thompson_stats = tc_model.get_trade_confidence(
                    strategy="iron_condor",
                    ticker=ticker,
                    regime=None,
                )

                # Get recent RAG lessons
                rag_lessons = []
                try:
                    rag = LessonsLearnedRAG()
                    results = rag.search("iron condor loss failure", top_k=3)
                    for lesson, _score in results:
                        rag_lessons.append(lesson.snippet[:200])
                except Exception:
                    pass

                opinion = get_trade_opinion(
                    vix_current=None,  # VIX already checked above
                    thompson_stats=thompson_stats,
                    regime=None,
                    recent_lessons=rag_lessons,
                )

                if opinion is not None:
                    logger.info("=" * 60)
                    logger.info("LLM PRE-TRADE OPINION (DeepSeek-R1)")
                    logger.info("=" * 60)
                    logger.info(f"Should trade: {opinion.should_trade}")
                    logger.info(f"Confidence: {opinion.confidence:.2f}")
                    logger.info(f"Regime: {opinion.regime}")
                    logger.info(f"Suggested delta: {opinion.suggested_short_delta}")
                    logger.info(f"Suggested DTE: {opinion.suggested_dte}")
                    logger.info(f"Reasoning: {opinion.reasoning}")
                    if opinion.risk_flags:
                        logger.warning(f"Risk flags: {opinion.risk_flags}")
                    logger.info("=" * 60)

                    telemetry.update_ticker_decision(
                        ticker,
                        gate=2,
                        status="PASS" if opinion.should_trade else "ADVISORY_SKIP",
                        indicators={
                            "llm_should_trade": bool(opinion.should_trade),
                            "llm_confidence": float(opinion.confidence),
                            "llm_regime": str(opinion.regime),
                        },
                    )

                    # Block trade if R1 says NO with high confidence
                    if not opinion.should_trade and opinion.confidence >= 0.7:
                        logger.warning(
                            f"BLOCKED by LLM research agent: {opinion.reasoning} "
                            f"(confidence: {opinion.confidence:.0%})"
                        )
                        telemetry.update_ticker_decision(
                            ticker,
                            gate=2,
                            status="REJECT",
                            rejection_reason=f"LLM advisory: {opinion.reasoning}",
                            indicators={
                                "llm_should_trade": bool(opinion.should_trade),
                                "llm_confidence": float(opinion.confidence),
                            },
                        )
                        return {
                            "success": False,
                            "reason": f"LLM advisory: {opinion.reasoning}",
                            "opinion": opinion.model_dump(),
                        }
                else:
                    logger.info(
                        "LLM pre-trade opinion: unavailable (proceeding with existing logic)"
                    )
            except Exception as e:
                logger.warning(
                    f"LLM pre-trade research failed: {e} (proceeding with existing logic)"
                )
        except Exception as e:
            logger.warning(f"Pre-trade enrichment failed: {e}")

        # Find trade
        ic = strategy.find_trade()
        if not ic:
            logger.error("Failed to find suitable iron condor")
            telemetry.update_ticker_decision(
                ticker,
                gate=3,
                status="REJECT",
                rejection_reason="no_trade_found",
            )
            return {"success": False, "reason": "no_trade_found"}

        # Execute - LIVE by default now!
        # LL-290 FIX: Acquire trade lock to prevent race conditions
        # Multiple workflow runs could pass position check simultaneously without lock
        try:
            with acquire_trade_lock(timeout=10):
                trade = strategy.execute(ic, live=live_mode, entry_reason=reason)
        except TradeLockTimeout:
            logger.warning("⚠️ Could not acquire trade lock - another trade may be in progress")
            telemetry.update_ticker_decision(
                ticker,
                gate=4,
                status="REJECT",
                rejection_reason="trade_lock_timeout",
            )
            return {"success": False, "reason": "trade_lock_timeout"}

        trade_status = str(trade.get("status") or "")
        if trade_status.startswith(("BLOCKED", "SKIPPED")):
            rejection_reason = str(trade.get("reason") or trade_status)
            telemetry.update_ticker_decision(
                ticker,
                gate=4,
                status="REJECT",
                rejection_reason=rejection_reason,
                indicators={"trade_status": trade_status},
            )
            logger.info("IRON CONDOR TRADER - COMPLETE (blocked)")
            return {"success": False, "reason": rejection_reason, "trade": trade}

        telemetry.update_ticker_decision(
            ticker,
            gate=9,
            status="EXECUTED",
            order_details={
                "strategy": "iron_condor",
                "symbol": ticker,
                "live": bool(live_mode),
                "expiry": getattr(ic, "expiry", None),
                "dte": getattr(ic, "dte", None),
                "short_put": getattr(ic, "short_put", None),
                "long_put": getattr(ic, "long_put", None),
                "short_call": getattr(ic, "short_call", None),
                "long_call": getattr(ic, "long_call", None),
            },
        )

        logger.info("IRON CONDOR TRADER - COMPLETE")
        return {"success": True, "trade": trade}
    finally:
        # Always persist a session_decisions artifact so North Star cadence/no-trade diagnostics
        # can explain why we did or did not trade.
        telemetry.save_session_decisions(session_profile)
        telemetry.print_session_summary()


if __name__ == "__main__":
    result = main()
    print(f"\nResult: {json.dumps(result, indent=2, default=str)}")
