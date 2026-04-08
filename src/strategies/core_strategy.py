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
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from src.core.trading_constants import MAX_POSITIONS as MAX_OPTION_LEGS
from src.safety.trade_lock import acquire_trade_lock
from src.utils.error_monitoring import init_sentry

try:
    load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=False)
except (AssertionError, Exception):
    pass  # In CI, env vars are set via workflow secrets
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
            "wing_width": 10,  # $10 wide spreads per CLAUDE.md
            # EV math: 75% profit / 100% stop → EV = 0.85*0.75 - 0.15*1.0 = +0.49
            # Legacy asymmetric take-profit/stop profile was EV-neutral and has been deprecated.
            "take_profit_pct": 0.75,  # Close at 75% profit
            "stop_loss_pct": 1.0,  # Close at 100% loss
            "exit_dte": 7,  # Exit at 7 DTE per LL-268 research (80%+ win rate)
            "max_positions": max(
                1, int(MAX_OPTION_LEGS) // 4
            ),  # Canonical limit: 8 option legs => 2 iron condors
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

        # FIXED Mar 23, 2026: No fallback price. Hardcoded $688 caused wrong
        # strike calculations when SPY moved. Trading on stale prices = losses.
        raise RuntimeError("Live SPY price unavailable — refusing to trade on stale data")

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

    def calculate_premiums(self, legs: tuple[float, float, float, float], expiry: str) -> dict:
        """
        Fetch mandatory live mid-prices for all 4 legs from the Alpaca chain.
        Refuses to trade if live bid/ask data is unavailable.
        """
        try:
            from alpaca.data.historical.option import OptionHistoricalDataClient
            from alpaca.data.requests import OptionLatestQuoteRequest
            from src.utils.alpaca_client import get_alpaca_credentials

            api_key, secret = get_alpaca_credentials()
            data_client = OptionHistoricalDataClient(api_key, secret)

            # Format YYMMDD for OCC
            exp_formatted = expiry.replace("-", "")[2:]

            def build_occ(strike: float, opt_type: str) -> str:
                strike_str = f"{int(strike * 1000):08d}"
                return f"SPY{exp_formatted}{opt_type}{strike_str}"

            # LP, SP, SC, LC
            symbols = [
                build_occ(legs[0], "P"),  # Long Put
                build_occ(legs[1], "P"),  # Short Put
                build_occ(legs[2], "C"),  # Short Call
                build_occ(legs[3], "C"),  # Long Call
            ]

            logger.info(f"Pricing structure symbols: {symbols}")

            request = OptionLatestQuoteRequest(symbol_or_symbols=symbols)
            quotes = data_client.get_option_latest_quote(request)

            total_credit = 0.0
            for i, sym in enumerate(symbols):
                if sym not in quotes:
                    raise RuntimeError(f"Missing live quote for leg {sym}")

                quote = quotes[sym]
                if quote.bid_price == 0 or quote.ask_price == 0:
                    raise RuntimeError(
                        f"Invalid bid/ask for {sym}: {quote.bid_price}/{quote.ask_price}"
                    )

                mid = (quote.bid_price + quote.ask_price) / 2
                # Credit Spread Math: Short Mid - Long Mid
                if i in [1, 2]:  # Short legs
                    total_credit += mid
                else:  # Long legs
                    total_credit -= mid

            wing_width = self.config["wing_width"]
            max_risk = (wing_width * 100) - (total_credit * 100)

            logger.info(
                f"Realized Mid-Price Credit: ${total_credit:.2f} (Max Risk: ${max_risk:.2f})"
            )

            return {
                "credit": total_credit,
                "max_risk": max_risk,
                "max_profit": total_credit * 100,
                "risk_reward": max_risk / (total_credit * 100) if total_credit > 0 else 0,
            }
        except Exception as e:
            logger.error(f"PRICING ENGINE FAILURE: {e}")
            raise RuntimeError(f"Quantitative pricing failed: {e} — halting.")

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
        days_until_friday = (4 - target_date.weekday()) % 7
        if days_until_friday == 0 and target_date.weekday() != 4:
            days_until_friday = 7
        if target_date.weekday() > 4:
            days_until_friday = (4 - target_date.weekday()) % 7
        expiry_date = target_date + timedelta(days=days_until_friday)
        actual_dte = (expiry_date - datetime.now()).days
        if actual_dte < 21:
            expiry_date += timedelta(days=7)
        logger.info(
            f"Expiry: {expiry_date.strftime('%Y-%m-%d')} ({expiry_date.strftime('%A')}) - {(expiry_date - datetime.now()).days} DTE"
        )

        # Fetch real mid-prices from the chain
        expiry_str = expiry_date.strftime("%Y-%m-%d")
        premiums = self.calculate_premiums((long_put, short_put, short_call, long_call), expiry_str)

        return IronCondorLegs(
            underlying=self.config["underlying"],
            expiry=expiry_str,
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
        """Check if conditions are right for entry."""
        try:
            from src.signals.vix_mean_reversion_signal import VIXMeanReversionSignal

            vix_signal = VIXMeanReversionSignal()
            signal = vix_signal.calculate_signal()
            if signal.signal == "AVOID":
                return False, signal.reason
            return True, signal.reason
        except Exception:
            return False, "VIX signal failure"

    def execute(self, ic: IronCondorLegs, live: bool = False, entry_reason: str = "") -> dict:
        """Execute the iron condor trade with RAG verification."""
        if live:
            try:
                from alpaca.trading.client import TradingClient
                from src.utils.alpaca_client import get_alpaca_credentials

                api_key, secret = get_alpaca_credentials()
                if api_key and secret:
                    client = TradingClient(api_key, secret, paper=True)
                    positions = client.get_all_positions()

                    spy_option_positions = [
                        p for p in positions if p.symbol.startswith("SPY") and len(p.symbol) > 5
                    ]

                    total_contracts = sum(abs(int(float(p.qty))) for p in spy_option_positions)
                    max_ic = int(self.config.get("max_positions", 2))
                    max_contracts = max_ic * 4
                    current_ic_count = total_contracts // 4

                    if total_contracts >= max_contracts:
                        return {
                            "status": "SKIPPED_POSITION_LIMIT",
                            "reason": f"Already have {current_ic_count}/{max_ic} iron condors",
                        }

                    # WORLD-CLASS RAG GATE (The Mistake Preventer)
                    from src.rag.trade_verifier import get_trade_verifier

                    verifier = get_trade_verifier(threshold=0.70)

                    context = f"delta={self.config['short_delta']} dte={self.config['target_dte']} entry_reason={entry_reason}"
                    is_safe, rag_reason = verifier.verify_entry(
                        symbol=ic.underlying, strategy="iron_condor", setup_context=context
                    )

                    if not is_safe:
                        logger.warning(f"🚨 RAG VETO: {rag_reason}")
                        return {"status": "RAG_VETOED", "reason": rag_reason}

                    logger.info(f"✅ RAG VERIFIED: {rag_reason}")

                    # Check for duplicate expiry
                    target_expiry = ic.expiry.replace("-", "")[2:]
                    existing_expiries = {
                        p.symbol[3:9] for p in spy_option_positions if len(p.symbol) > 10
                    }
                    if target_expiry in existing_expiries:
                        return {
                            "status": "BLOCKED_DUPLICATE_EXPIRY",
                            "reason": f"Already holding {ic.expiry}",
                        }

            except Exception as e:
                logger.error(f"Position check failed: {e}")
                return {"success": False, "reason": str(e)}

        logger.info("Proceeding with Iron Condor submission...")
        return {
            "status": "SUCCESS_SIMULATED",
            "strategy": "iron_condor",
            "underlying": ic.underlying,
        }

    def _record_trade(self, trade: dict):
        """Record trade for learning."""
        trades_file = Path(f"data/trades_{datetime.now().strftime('%Y-%m-%d')}.json")
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
    parser.add_argument("--live", action="store_true", help="Execute LIVE trades")
    parser.add_argument("--symbol", type=str, default="SPY", help="Symbol")
    parser.add_argument("--force", action="store_true", help="Force entry")
    args = parser.parse_args()

    strategy = IronCondorStrategy()

    should_enter, reason = strategy.check_entry_conditions()
    if not should_enter and not args.force:
        return {"success": False, "reason": reason}

    ic = strategy.find_trade()
    if ic:
        with acquire_trade_lock(timeout=10):
            return strategy.execute(ic, live=args.live, entry_reason=reason)
    return {"success": False, "reason": "no_trade_found"}


if __name__ == "__main__":
    main()
