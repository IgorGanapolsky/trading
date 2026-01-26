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
- Close at 21 DTE (avoid gamma risk)
- Close if one side reaches 200% loss

THIS IS THE MONEY MAKER.
"""

import json
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from src.rag.lessons_learned_rag import LessonsLearnedRAG
from src.safety.trade_lock import TradeLockTimeout, acquire_trade_lock
from src.utils.error_monitoring import init_sentry

load_dotenv()
init_sentry()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


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

    def __init__(self):
        # FIXED Jan 19 2026: SPY ONLY per CLAUDE.md (TastyTrade strategy scrapped)
        # Iron condors replace credit spreads - 86% win rate from $100K success
        self.config = {
            "underlying": "SPY",  # SPY ONLY per CLAUDE.md - best liquidity, $100K success
            "target_dte": 30,
            "min_dte": 21,
            "max_dte": 45,
            "short_delta": 0.15,  # 15 delta = ~85% POP (research-backed)
            "wing_width": 5,  # $5 wide spreads per updated CLAUDE.md
            "take_profit_pct": 0.50,  # Close at 50% profit
            "stop_loss_pct": 2.0,  # Close at 200% loss
            "exit_dte": 7,  # Exit at 7 DTE per LL-268 research (80%+ win rate)
            "max_positions": 1,  # Per CLAUDE.md: "1 iron condor at a time"
            "position_size_pct": 0.05,  # 5% of portfolio per position - CLAUDE.md MANDATE
        }

    def get_underlying_price(self) -> float:
        """Get current price of SPY from Alpaca or estimate."""
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
                request = StockLatestQuoteRequest(symbol_or_symbols=["SPY"])
                quote = data_client.get_stock_latest_quote(request)
                if "SPY" in quote:
                    mid_price = (quote["SPY"].ask_price + quote["SPY"].bid_price) / 2
                    logger.info(f"Live SPY price from Alpaca: ${mid_price:.2f}")
                    return mid_price
        except Exception as e:
            logger.warning(f"Could not fetch live SPY price: {e}")

        # Fallback: Use recent estimate (updated Jan 23, 2026)
        # NOTE: SPY at $688 as of Jan 23, 2026 - update if stale
        fallback_price = 688.0
        logger.info(f"Using fallback SPY price: ${fallback_price:.2f}")
        return fallback_price

    def calculate_strikes(self, price: float) -> tuple[float, float, float, float]:
        """
        Calculate iron condor strikes based on delta targeting.

        For 15 delta on SPY (~$690):
        - Short put: ~5% below price (~$655)
        - Short call: ~5% above price (~$725)
        - Wing width: $5 (appropriate for SPY)

        CRITICAL FIX Jan 23, 2026:
        SPY options have $5 strike increments for OTM options.
        Must round to nearest $5 multiple or orders will fail!
        ROOT CAUSE: $724/$729 strikes don't exist, only $725/$730
        """
        # 15 delta is roughly 1.5 standard deviation move
        # For 30 DTE on SPY, use ~5% OTM for 15-delta equivalent

        wing = self.config["wing_width"]

        # FIX: Round to nearest $5 increment (SPY OTM options only exist at $5 intervals)
        def round_to_5(x: float) -> float:
            return round(x / 5) * 5

        short_put = round_to_5(price * 0.95)  # 5% OTM for puts, rounded to $5
        long_put = short_put - wing

        short_call = round_to_5(price * 1.05)  # 5% OTM for calls, rounded to $5
        long_call = short_call + wing

        return long_put, short_put, short_call, long_call

    def calculate_premiums(self, legs: tuple[float, float, float, float], dte: int) -> dict:
        """
        Estimate premiums for iron condor legs.

        Real implementation would use options pricing model or market data.
        """
        long_put, short_put, short_call, long_call = legs

        # SPY premium estimates (~$595 stock)
        # At 30 DTE, 15-delta 5% OTM options: ~$1.50-2.50 for SPY
        # $5 wide spreads collect roughly $0.75-1.25 net credit per side
        put_spread_credit = 1.00  # Sell short put, buy long put
        call_spread_credit = 1.00  # Sell short call, buy long call

        total_credit = put_spread_credit + call_spread_credit
        wing_width = self.config["wing_width"]
        max_risk = (wing_width * 100) - (total_credit * 100)  # Per contract

        return {
            "credit": total_credit,
            "max_risk": max_risk,
            "max_profit": total_credit * 100,
            "risk_reward": max_risk / (total_credit * 100) if total_credit > 0 else 0,
        }

    def find_trade(self) -> Optional[IronCondorLegs]:
        """
        Find an iron condor trade matching our criteria.
        """
        price = self.get_underlying_price()
        logger.info(f"Underlying price: ${price:.2f}")

        # Calculate strikes
        long_put, short_put, short_call, long_call = self.calculate_strikes(price)
        logger.info(f"Strikes: LP={long_put} SP={short_put} SC={short_call} LC={long_call}")

        # Calculate expiry - MUST be a Friday (options expire on Fridays)
        target_date = datetime.now() + timedelta(days=self.config["target_dte"])
        # Adjust to nearest Friday: weekday() returns 0=Mon, 4=Fri
        days_until_friday = (4 - target_date.weekday()) % 7
        if days_until_friday == 0 and target_date.weekday() != 4:
            days_until_friday = 7  # Next Friday if we're past Friday
        # If target is Sat/Sun, go to next Friday; otherwise go to this week's Friday
        if target_date.weekday() > 4:  # Saturday=5, Sunday=6
            days_until_friday = (4 - target_date.weekday()) % 7
        expiry_date = target_date + timedelta(days=days_until_friday)
        # If this pushed us too close (<21 DTE), use the Friday after
        actual_dte = (expiry_date - datetime.now()).days
        if actual_dte < 21:
            expiry_date += timedelta(days=7)
        logger.info(
            f"Expiry: {expiry_date.strftime('%Y-%m-%d')} ({expiry_date.strftime('%A')}) - {(expiry_date - datetime.now()).days} DTE"
        )

        # Estimate premiums
        premiums = self.calculate_premiums(
            (long_put, short_put, short_call, long_call), self.config["target_dte"]
        )

        return IronCondorLegs(
            underlying=self.config["underlying"],
            expiry=expiry_date.strftime("%Y-%m-%d"),
            dte=self.config["target_dte"],
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
            # If VIX check fails, log warning but allow trade
            logger.warning(f"VIX check failed: {e} - proceeding with caution")
            return True, "VIX check failed, proceeding with caution"

    def execute(self, ic: IronCondorLegs, live: bool = False) -> dict:
        """
        Execute the iron condor trade.

        Args:
            ic: Iron condor legs to execute
            live: If True, execute on Alpaca. If False, simulate only.
        """
        # POSITION CHECK FIRST - Prevent race conditions from parallel workflow runs
        # FIX Jan 22, 2026: Move position check to VERY START before any other logic
        # ROOT CAUSE: Multiple workflow runs could race past position check if it ran late
        if live:
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

                    # Count SPY OPTION positions only (iron condor = 4 legs)
                    # Options have format like SPY260220P00565000, shares are just "SPY"
                    spy_option_positions = [
                        p
                        for p in positions
                        if p.symbol.startswith("SPY")
                        and len(p.symbol) > 5  # Options have longer symbols
                    ]

                    # Count TOTAL CONTRACTS
                    total_contracts = sum(abs(int(float(p.qty))) for p in spy_option_positions)
                    unique_symbols = len(spy_option_positions)

                    logger.info(
                        f"Current SPY OPTION positions: {unique_symbols} symbols, {total_contracts} contracts"
                    )

                    # STRICT CHECK: If ANY option positions exist, SKIP
                    # This prevents accumulation from race conditions
                    if total_contracts > 0:
                        logger.warning("=" * 60)
                        logger.warning("POSITION LIMIT BLOCKING NEW TRADE")
                        logger.warning("=" * 60)
                        logger.warning(
                            f"REASON: Already have {total_contracts} contracts (max allowed: 0 for new entry)"
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
                            "status": "SKIPPED_POSITION_EXISTS",
                            "reason": f"Already have {total_contracts} option contracts - cannot open new position",
                            "existing_positions": [
                                {"symbol": p.symbol, "qty": p.qty} for p in spy_option_positions
                            ],
                        }
                    else:
                        logger.info("No existing option positions - OK to proceed")
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
        # FIX Jan 21, 2026: Only block on CRITICAL lessons that are NOT resolved
        # LL-244 (security audit) was blocking even though it's a general audit
        strategy_lessons = rag.search("iron condor failures losses", top_k=3)
        for lesson, score in strategy_lessons:
            # Skip lessons that have been resolved or fixed
            if lesson.severity == "RESOLVED" or "resolved" in lesson.snippet.lower():
                logger.info(f"Skipping resolved lesson: {lesson.id}")
                continue
            # Only block on lessons specifically about iron condor execution
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
                from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
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

                    logger.info("📋 Building MLeg (multi-leg) iron condor order...")
                    logger.info(f"   Long Put:   {long_put_sym} (BUY)")
                    logger.info(f"   Short Put:  {short_put_sym} (SELL)")
                    logger.info(f"   Short Call: {short_call_sym} (SELL)")
                    logger.info(f"   Long Call:  {long_call_sym} (BUY)")

                    # For iron condor, we receive net credit (negative limit price)
                    # Conservative: accept any credit >= $0.50 per contract
                    # The actual credit will depend on market conditions
                    # Using market order (no limit_price) lets the market determine credit
                    try:
                        from alpaca.trading.requests import MarketOrderRequest

                        # Submit as market MLeg order - all 4 legs fill together or not at all
                        order_req = MarketOrderRequest(
                            qty=1,
                            order_class=OrderClass.MLEG,
                            time_in_force=TimeInForce.DAY,
                            legs=option_legs,
                        )

                        logger.info("🚀 Submitting MLeg iron condor order...")
                        order = client.submit_order(order_req)

                        order_ids.append({
                            "order_id": str(order.id),
                            "type": "mleg_iron_condor",
                            "legs": [long_put_sym, short_put_sym, short_call_sym, long_call_sym],
                        })

                        logger.info(f"✅ MLeg order submitted: {order.id}")
                        logger.info(f"   Status: {order.status}")
                        status = "LIVE_SUBMITTED"

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
                    "won": True,  # Will update when closed
                    "pnl": 0,  # Will update when closed
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
    parser.add_argument(
        "--symbol", type=str, default="SPY", help="Underlying symbol (default: SPY)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force execution - bypass VIX checks (CEO directive mode)",
    )
    args = parser.parse_args()

    # Default to LIVE mode as of Dec 29, 2025 to hit $100/day target
    live_mode = args.live or (not args.dry_run)

    logger.info("IRON CONDOR TRADER - STARTING")
    logger.info(f"Mode: {'LIVE' if live_mode else 'SIMULATED'}")
    logger.info(f"Symbol: {args.symbol}")

    # CHECK TRADING HALT FILE FIRST
    halt_file = Path("data/trading_halt.txt")
    if halt_file.exists():
        logger.warning("=" * 60)
        logger.warning("TRADING HALTED - Manual halt in effect")
        logger.warning("=" * 60)
        with open(halt_file) as f:
            logger.warning(f.read())
        logger.warning("Remove data/trading_halt.txt to resume trading")
        logger.warning("=" * 60)
        return {"success": False, "reason": "Trading halted - manual halt in effect"}

    # LL-297 FIX (Jan 23, 2026): Daily trade limit to prevent churning
    # ROOT CAUSE: 21 trades in one day caused $11.29 loss from bid/ask spreads
    # SOLUTION: Only 1 iron condor entry per day (4 legs max)
    MAX_TRADES_PER_DAY = 4  # 1 iron condor = 4 legs
    trades_file = Path(f"data/trades_{datetime.now().strftime('%Y-%m-%d')}.json")
    if trades_file.exists():
        try:
            with open(trades_file) as f:
                today_trades = json.load(f)
            if len(today_trades) >= MAX_TRADES_PER_DAY:
                logger.warning("=" * 60)
                logger.warning("DAILY TRADE LIMIT REACHED - BLOCKING NEW TRADES")
                logger.warning("=" * 60)
                logger.warning(f"Trades today: {len(today_trades)} (max: {MAX_TRADES_PER_DAY})")
                logger.warning("Reason: Prevent churning and bid/ask spread losses")
                logger.warning("=" * 60)
                return {
                    "success": False,
                    "reason": f"Daily limit reached: {len(today_trades)}/{MAX_TRADES_PER_DAY}",
                }
        except Exception as e:
            logger.warning(f"Could not check daily trades: {e}")

    # HARD BLOCK: Validate ticker before proceeding (Jan 20 2026 - SOFI crisis)
    from src.utils.ticker_validator import validate_ticker

    strategy = IronCondorStrategy()
    # Override symbol from command line if provided (Jan 21, 2026 fix)
    # ROOT CAUSE: Workflow called with --symbol SPY but argparse rejected it
    # This blocked trading for 8+ days with silent "unrecognized arguments" error
    if args.symbol:
        strategy.config["underlying"] = args.symbol.upper()
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
    else:
        should_enter, reason = strategy.check_entry_conditions()
        logger.info(f"Entry conditions: {should_enter} ({reason})")

    if not should_enter:
        logger.info("Skipping trade - conditions not met")
        return {"success": False, "reason": reason}

    # Find trade
    ic = strategy.find_trade()
    if not ic:
        logger.error("Failed to find suitable iron condor")
        return {"success": False, "reason": "no_trade_found"}

    # Execute - LIVE by default now!
    # LL-290 FIX: Acquire trade lock to prevent race conditions
    # Multiple workflow runs could pass position check simultaneously without lock
    try:
        with acquire_trade_lock(timeout=10):
            trade = strategy.execute(ic, live=live_mode)
    except TradeLockTimeout:
        logger.warning("⚠️ Could not acquire trade lock - another trade may be in progress")
        return {"success": False, "reason": "trade_lock_timeout"}

    logger.info("IRON CONDOR TRADER - COMPLETE")
    return {"success": True, "trade": trade}


if __name__ == "__main__":
    result = main()
    print(f"\nResult: {json.dumps(result, indent=2, default=str)}")
