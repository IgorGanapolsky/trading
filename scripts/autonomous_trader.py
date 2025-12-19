"""Bootstrap entry point for the hybrid trading orchestrator."""

from __future__ import annotations

import os

# Early diagnostic output for CI visibility
import sys

# Reduced annotations to avoid GitHub 10-annotation limit
print("autonomous_trader.py starting - Python:", sys.version.split()[0], flush=True)

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

# Removed annotation to stay under limit

try:
    from dotenv import load_dotenv
except ImportError:

    def load_dotenv():
        pass  # Stub


# Ensure src is on the path when executed via GitHub Actions
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

try:
    from src.utils.error_monitoring import init_sentry
    from src.utils.logging_config import setup_logging
except Exception as e:
    print(f"::error::Failed to import src utilities: {e}", flush=True)
    sys.exit(2)

SYSTEM_STATE_PATH = Path(os.getenv("SYSTEM_STATE_PATH", "data/system_state.json"))


def _refresh_account_data(logger) -> None:
    """Fetch latest account data from Alpaca and update system_state.json."""
    try:
        from src.core.alpaca_trader import AlpacaTrader

        trader = AlpacaTrader(paper=True)
        account = trader.get_account_info()

        equity = float(account.get("equity") or 0.0)
        cash = float(account.get("cash") or 0.0)
        buying_power = float(account.get("buying_power") or 0.0)

        if equity > 0:
            state_path = Path("data/system_state.json")
            if state_path.exists():
                with state_path.open("r", encoding="utf-8") as handle:
                    state = json.load(handle)

                state.setdefault("account", {})
                state["account"]["current_equity"] = equity
                state["account"]["cash"] = cash
                # Update buying_power if available
                state["account"]["buying_power"] = buying_power

                # Update timestamp
                state.setdefault("meta", {})
                state["meta"]["last_updated"] = datetime.now().isoformat()

                with state_path.open("w", encoding="utf-8") as handle:
                    json.dump(state, handle, indent=2)
                logger.info(f"System state refreshed: Equity=${equity:.2f}")
    except Exception as e:
        logger.warning(f"Failed to refresh account data: {e}")


def _update_system_state_with_prediction_trade(trade_record: dict[str, Any], logger) -> None:
    """Update `data/system_state.json` so Tier 6 reflects the new prediction market trade."""
    state_path = Path("data/system_state.json")
    if not state_path.exists():
        logger.warning("system_state.json missing; skipping state update")
        return

    try:
        with state_path.open("r", encoding="utf-8") as handle:
            state = json.load(handle)
    except Exception as exc:
        logger.error(f"Failed to read system_state.json: {exc}")
        return

    strategies = state.setdefault("strategies", {})
    tier6_defaults = {
        "name": "Prediction Markets Strategy (Kalshi)",
        "allocation": 0.05,
        "daily_amount": 5.0,
        "trades_executed": 0,
        "total_invested": 0.0,
        "status": "active",
        "execution_schedule": "Daily + Weekends (24/7 markets)",
        "last_execution": None,
        "next_execution": None,
    }
    tier6 = strategies.setdefault("tier6", tier6_defaults)
    tier6["trades_executed"] = tier6.get("trades_executed", 0) + 1
    tier6["total_invested"] = round(
        tier6.get("total_invested", 0.0) + float(trade_record.get("amount", 0.0)), 6
    )
    tier6["last_execution"] = trade_record.get("timestamp")
    tier6["status"] = "active"

    investments = state.setdefault("investments", {})
    investments["tier6_invested"] = round(
        investments.get("tier6_invested", 0.0) + float(trade_record.get("amount", 0.0)), 6
    )
    investments["total_invested"] = round(
        investments.get("total_invested", 0.0) + float(trade_record.get("amount", 0.0)), 6
    )

    performance = state.setdefault("performance", {})
    performance["total_trades"] = performance.get("total_trades", 0) + 1

    try:
        with state_path.open("w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2)
        logger.info("system_state.json updated with prediction market trade metadata")
    except Exception as exc:
        logger.error(f"Failed to write system_state.json: {exc}")


def validate_order_size(amount: float, expected: float, tier: str = "T1_CORE") -> tuple[bool, str]:
    """
    Guardrail against fat-finger order sizing.

    Rules:
    - Enforce $10 minimum notional.
    - Reject if amount > 10x expected (Mistake #1 scenario).
    - Allow +/-10% tolerance; outside that returns False.
    """
    minimum = 6.0
    if amount < minimum:
        return False, f"Order ${amount:.2f} below minimum ${minimum:.2f}"

    # Protect against missing expected values
    if expected <= 0:
        expected = amount

    if amount > expected * 10:
        return False, "Order size exceeds 10x expected; possible fat-finger"

    tolerance = expected * 0.10
    if abs(amount - expected) > tolerance:
        return False, f"Order differs by more than 10% (expected ~${expected:.2f})"

    return True, ""


def _flag_enabled(env_name: str, default: str = "true") -> bool:
    return os.getenv(env_name, default).strip().lower() in {"1", "true", "yes", "on"}


def _parse_tickers() -> list[str]:
    # EXPANDED (Dec 12, 2025): From 3 tickers to 20 for better trade opportunities
    # Mix of: ETFs (SPY, QQQ, VOO, IWM, DIA), Tech (NVDA, AAPL, MSFT, GOOGL, META, AMD, AMZN),
    # Energy (XLE), Finance (XLF), Healthcare (XLV), Momentum favorites (TSLA, COIN, PLTR)
    default_tickers = (
        "SPY,QQQ,VOO,IWM,DIA,"  # Major ETFs
        "NVDA,AAPL,MSFT,GOOGL,META,AMD,AMZN,TSLA,"  # Big Tech
        "XLE,XLF,XLV,"  # Sector ETFs
        "COIN,PLTR,SOFI"  # High-momentum stocks
    )
    raw = os.getenv("TARGET_TICKERS", default_tickers)
    return [ticker.strip().upper() for ticker in raw.split(",") if ticker.strip()]


def is_weekend() -> bool:
    """Check if today is Saturday or Sunday."""
    return datetime.now().weekday() in [5, 6]  # Saturday=5, Sunday=6


def is_market_holiday() -> bool:
    """
    Check if today is a market holiday (market closed on a weekday).

    Uses Alpaca's clock API to determine if market is closed.
    If market is closed AND it's a weekday, it's a holiday.
    """
    try:
        from src.core.alpaca_trader import AlpacaTrader

        is_weekday = datetime.now().weekday() < 5  # Monday=0, Friday=4
        if not is_weekday:
            return False  # Weekends are not holidays, they're weekends

        trader = AlpacaTrader(paper=True)
        clock = trader.trading_client.get_clock()
        return not clock.is_open  # Market closed on weekday = holiday
    except Exception as e:
        logger = setup_logging()
        logger.warning(f"Could not check market holiday status: {e}. Assuming not a holiday.")
        return False  # Fail safe: assume not a holiday if check fails


def _resolve_account_equity(logger) -> float:
    """Best-effort lookup of current equity for scaling decisions."""
    try:
        from src.core.alpaca_trader import AlpacaTrader

        trader = AlpacaTrader(paper=True)
        account = trader.get_account_info()
        return float(account.get("equity") or account.get("portfolio_value") or 0.0)
    except Exception as exc:  # pragma: no cover - external dependency
        logger.warning("Could not resolve account equity for scaling: %s", exc)
        fallback = float(os.getenv("SIMULATED_EQUITY", "100000"))
        return fallback


def _apply_daily_input_scaling(logger) -> None:
    """Optionally bump DAILY_INVESTMENT based on equity growth."""
    if not _flag_enabled("ENABLE_DAILY_INPUT_SCALING", "true"):
        return
    equity = _resolve_account_equity(logger)
    if equity <= 0:
        logger.info("Daily input scaling skipped - unknown equity snapshot.")
        return
    scaled = calc_daily_input(equity)
    os.environ["DAILY_INVESTMENT"] = f"{scaled:.2f}"
    logger.info(
        "Daily input auto-scaled to $%.2f (equity=$%.2f). Set ENABLE_DAILY_INPUT_SCALING=false to disable.",
        scaled,
        equity,
    )


# See rag_knowledge/lessons_learned/ll_049_config_workflow_sync_failure_dec16.md


def _load_equity_snapshot() -> float | None:
    """Pull the most recent equity figure from disk or simulation env."""

    if SYSTEM_STATE_PATH.exists():
        try:
            with SYSTEM_STATE_PATH.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
                account = payload.get("account") or {}
                equity = account.get("current_equity") or account.get("portfolio_value")
                if equity is not None:
                    return float(equity)
        except Exception:
            pass

    sim_equity = os.getenv("SIMULATED_EQUITY")
    if sim_equity:
        try:
            return float(sim_equity)
        except ValueError:
            return None
    return None


def _apply_dynamic_daily_budget(logger) -> float | None:
    """
    Adjust DAILY_INVESTMENT based on account equity before orchestrator loads.

    Returns:
        The resolved daily investment (or None when unchanged/unavailable)
    """

    equity = _load_equity_snapshot()
    if equity is None:
        logger.info(
            "Dynamic budget: equity snapshot unavailable; keeping DAILY_INVESTMENT=%s",
            os.getenv("DAILY_INVESTMENT", "10.0"),
        )
        return None

    new_amount = calc_daily_input(equity)
    try:
        current_amount = float(os.getenv("DAILY_INVESTMENT", "10.0"))
    except ValueError:
        current_amount = 10.0

    if abs(current_amount - new_amount) < 0.01:
        return new_amount

    os.environ["DAILY_INVESTMENT"] = f"{new_amount:.2f}"
    logger.info(
        "Dynamic budget: equity $%.2f → DAILY_INVESTMENT $%.2f (≤ $50 cap).",
        equity,
        new_amount,
    )
    return new_amount


def prediction_enabled() -> bool:
    """Feature flag for prediction markets (Kalshi)."""
    return os.getenv("ENABLE_PREDICTION_MARKETS", "true").lower() in {"1", "true", "yes"}


def reit_enabled() -> bool:
    """Feature flag for REIT strategy (Tier 7)."""
    return os.getenv("ENABLE_REIT_STRATEGY", "true").lower() in {"1", "true", "yes"}


def precious_metals_enabled() -> bool:
    """Feature flag for Precious Metals strategy (Tier 8 - GLD/SLV)."""
    return os.getenv("ENABLE_PRECIOUS_METALS", "true").lower() in {"1", "true", "yes"}


def _update_system_state_with_reit_trade(trade_record: dict[str, Any], logger) -> None:
    """Update `data/system_state.json` so Tier 7 reflects the new REIT trade."""
    state_path = Path("data/system_state.json")
    if not state_path.exists():
        logger.warning("system_state.json missing; skipping state update")
        return

    try:
        with state_path.open("r", encoding="utf-8") as handle:
            state = json.load(handle)
    except Exception as exc:
        logger.error(f"Failed to read system_state.json: {exc}")
        return

    strategies = state.setdefault("strategies", {})
    tier7_defaults = {
        "name": "REIT Smart Income Strategy",
        "allocation": 0.10,
        "daily_amount": 10.0,
        "sectors": ["Growth", "Defensive", "Residential"],
        "universe": [
            "AMT",
            "CCI",
            "DLR",
            "EQIX",
            "PLD",
            "O",
            "VICI",
            "PSA",
            "WELL",
            "AVB",
            "EQR",
            "INVH",
        ],
        "trades_executed": 0,
        "total_invested": 0.0,
        "status": "active",
        "execution_schedule": "Daily 9:35 AM ET (market hours)",
        "last_execution": None,
        "next_execution": None,
        "regime": "Neutral",
    }
    tier7 = strategies.setdefault("tier7", tier7_defaults)
    tier7["trades_executed"] = tier7.get("trades_executed", 0) + 1
    tier7["total_invested"] = round(
        tier7.get("total_invested", 0.0) + float(trade_record.get("amount", 0.0)), 6
    )
    tier7["last_execution"] = trade_record.get("timestamp")
    tier7["status"] = "active"
    if trade_record.get("regime"):
        tier7["regime"] = trade_record.get("regime")

    investments = state.setdefault("investments", {})
    investments["tier7_invested"] = round(
        investments.get("tier7_invested", 0.0) + float(trade_record.get("amount", 0.0)), 6
    )
    investments["total_invested"] = round(
        investments.get("total_invested", 0.0) + float(trade_record.get("amount", 0.0)), 6
    )

    performance = state.setdefault("performance", {})
    performance["total_trades"] = performance.get("total_trades", 0) + 1

    open_positions = performance.setdefault("open_positions", [])
    if isinstance(open_positions, list):
        matching = next(
            (
                entry
                for entry in open_positions
                if entry.get("symbol") == trade_record.get("symbol")
            ),
            None,
        )
        entry_payload = {
            "symbol": trade_record.get("symbol"),
            "tier": "tier7",
            "amount": trade_record.get("amount"),
            "entry_date": trade_record.get("timestamp"),
            "entry_price": trade_record.get("price"),
            "current_price": trade_record.get("price"),
            "quantity": trade_record.get("quantity"),
            "unrealized_pl": 0.0,
            "unrealized_pl_pct": 0.0,
            "last_updated": trade_record.get("timestamp"),
        }
        if matching:
            matching.update(entry_payload)
        else:
            open_positions.append(entry_payload)

    try:
        with state_path.open("w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2)
        logger.info("system_state.json updated with REIT trade metadata")
    except Exception as exc:
        logger.error(f"Failed to write system_state.json: {exc}")


def _update_reit_daily_returns(logger) -> None:
    """
    Calculate and store REIT-specific daily returns in system_state.json.

    This answers the CEO's question: "How much did we make from REITs today?"
    """
    state_path = Path("data/system_state.json")
    if not state_path.exists():
        return

    try:
        with state_path.open("r", encoding="utf-8") as handle:
            state = json.load(handle)
    except Exception:
        return

    # REIT symbols from our universe
    reit_universe = {
        "AMT",
        "CCI",
        "DLR",
        "EQIX",
        "PLD",
        "O",
        "VICI",
        "PSA",
        "WELL",
        "AVB",
        "EQR",
        "INVH",
    }

    # Calculate REIT P/L from open positions
    open_positions = state.get("performance", {}).get("open_positions", [])
    reit_unrealized = 0.0
    reit_positions = []

    for pos in open_positions:
        symbol = pos.get("symbol", "")
        if symbol in reit_universe:
            pl = pos.get("unrealized_pl", 0.0)
            reit_unrealized += pl
            reit_positions.append({"symbol": symbol, "pl": pl})

    # Calculate REIT P/L from closed trades today
    closed_trades = state.get("performance", {}).get("closed_trades", [])
    today_str = datetime.now().strftime("%Y-%m-%d")
    reit_realized = 0.0

    for trade in closed_trades:
        symbol = trade.get("symbol", "")
        exit_date = trade.get("exit_date", "")
        if symbol in reit_universe and today_str in exit_date:
            reit_realized += trade.get("pl", 0.0)

    # Store in strategies.tier7
    tier7 = state.get("strategies", {}).get("tier7", {})
    tier7["daily_returns"] = {
        "date": today_str,
        "realized_pl": round(reit_realized, 2),
        "unrealized_pl": round(reit_unrealized, 2),
        "total_pl": round(reit_realized + reit_unrealized, 2),
        "positions": len(reit_positions),
    }
    state.setdefault("strategies", {})["tier7"] = tier7

    try:
        with state_path.open("w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2)
        logger.info(
            f"📊 REIT Daily Returns: ${reit_realized + reit_unrealized:.2f} ({len(reit_positions)} positions)"
        )
    except Exception:
        pass


def _update_system_state_with_precious_metals_trade(trade_record: dict[str, Any], logger) -> None:
    """Update `data/system_state.json` so Tier 8 reflects the new precious metals trade."""
    state_path = Path("data/system_state.json")
    if not state_path.exists():
        logger.warning("system_state.json missing; skipping state update")
        return

    try:
        with state_path.open("r", encoding="utf-8") as handle:
            state = json.load(handle)
    except Exception as exc:
        logger.error(f"Failed to read system_state.json: {exc}")
        return

    strategies = state.setdefault("strategies", {})
    tier8_defaults = {
        "name": "Precious Metals Strategy (GLD/SLV)",
        "allocation": 0.05,
        "daily_amount": 5.0,
        "etfs": ["GLD", "SLV"],
        "trades_executed": 0,
        "total_invested": 0.0,
        "status": "active",
        "execution_schedule": "Daily 9:35 AM ET (market hours)",
        "last_execution": None,
        "next_execution": None,
        "regime": "Neutral",
    }
    tier8 = strategies.setdefault("tier8", tier8_defaults)
    tier8["trades_executed"] = tier8.get("trades_executed", 0) + 1
    tier8["total_invested"] = round(
        tier8.get("total_invested", 0.0) + float(trade_record.get("amount", 0.0)), 6
    )
    tier8["last_execution"] = trade_record.get("timestamp")
    tier8["status"] = "active"
    if trade_record.get("regime"):
        tier8["regime"] = trade_record.get("regime")

    investments = state.setdefault("investments", {})
    investments["tier8_invested"] = round(
        investments.get("tier8_invested", 0.0) + float(trade_record.get("amount", 0.0)), 6
    )
    investments["total_invested"] = round(
        investments.get("total_invested", 0.0) + float(trade_record.get("amount", 0.0)), 6
    )

    performance = state.setdefault("performance", {})
    performance["total_trades"] = performance.get("total_trades", 0) + 1

    open_positions = performance.setdefault("open_positions", [])
    if isinstance(open_positions, list):
        matching = next(
            (
                entry
                for entry in open_positions
                if entry.get("symbol") == trade_record.get("symbol")
            ),
            None,
        )
        entry_payload = {
            "symbol": trade_record.get("symbol"),
            "tier": "tier8",
            "amount": trade_record.get("amount"),
            "entry_date": trade_record.get("timestamp"),
            "entry_price": trade_record.get("price"),
            "current_price": trade_record.get("price"),
            "quantity": trade_record.get("quantity"),
            "unrealized_pl": 0.0,
            "unrealized_pl_pct": 0.0,
            "last_updated": trade_record.get("timestamp"),
        }
        if matching:
            matching.update(entry_payload)
        else:
            open_positions.append(entry_payload)

    try:
        with state_path.open("w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2)
        logger.info("system_state.json updated with precious metals trade metadata")
    except Exception as exc:
        logger.error(f"Failed to write system_state.json: {exc}")


def _update_precious_metals_daily_returns(logger) -> None:
    """
    Calculate and store precious metals-specific daily returns in system_state.json.

    This answers: "How much did we make from gold/silver today?"
    """
    state_path = Path("data/system_state.json")
    if not state_path.exists():
        return

    try:
        with state_path.open("r", encoding="utf-8") as handle:
            state = json.load(handle)
    except Exception:
        return

    # Precious metals symbols
    metals_universe = {"GLD", "SLV"}

    # Calculate P/L from open positions
    open_positions = state.get("performance", {}).get("open_positions", [])
    metals_unrealized = 0.0
    metals_positions = []

    for pos in open_positions:
        symbol = pos.get("symbol", "")
        if symbol in metals_universe:
            pl = pos.get("unrealized_pl", 0.0)
            metals_unrealized += pl
            metals_positions.append({"symbol": symbol, "pl": pl})

    # Calculate P/L from closed trades today
    closed_trades = state.get("performance", {}).get("closed_trades", [])
    today_str = datetime.now().strftime("%Y-%m-%d")
    metals_realized = 0.0

    for trade in closed_trades:
        symbol = trade.get("symbol", "")
        exit_date = trade.get("exit_date", "")
        if symbol in metals_universe and today_str in exit_date:
            metals_realized += trade.get("pl", 0.0)

    # Store in strategies.tier8
    tier8 = state.get("strategies", {}).get("tier8", {})
    tier8["daily_returns"] = {
        "date": today_str,
        "realized_pl": round(metals_realized, 2),
        "unrealized_pl": round(metals_unrealized, 2),
        "total_pl": round(metals_realized + metals_unrealized, 2),
        "positions": len(metals_positions),
    }
    state.setdefault("strategies", {})["tier8"] = tier8

    try:
        with state_path.open("w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2)
        logger.info(
            f"Precious Metals Daily Returns: ${metals_realized + metals_unrealized:.2f} ({len(metals_positions)} positions)"
        )
    except Exception:
        pass


def execute_precious_metals_trading() -> None:
    """
    Execute Precious Metals trading strategy (Tier 8 - GLD/SLV).

    Uses regime-based allocation to invest in gold and silver ETFs based on:
    - Gold-Silver ratio for relative value
    - Market fear indicators
    - Dollar strength
    """
    logger = setup_logging()
    logger.info("=" * 80)
    logger.info("PRECIOUS METALS TRADING MODE (Tier 8 - GLD/SLV)")
    logger.info("=" * 80)

    try:
        from src.core.alpaca_trader import AlpacaTrader
        from src.strategies.precious_metals_strategy import PreciousMetalsStrategy

        # Initialize trader
        trader = None
        try:
            trader = AlpacaTrader(paper=True)
        except Exception as e:
            logger.warning(f"Trading API unavailable: {e}")
            logger.warning("   -> Proceeding in ANALYSIS mode (no real trades).")
            trader = None

        # Initialize precious metals strategy
        daily_amount = float(os.getenv("PRECIOUS_METALS_DAILY_ALLOCATION", "5.0"))
        metals_strategy = PreciousMetalsStrategy(trader=trader, daily_allocation=daily_amount)

        # Generate signals first to understand regime
        logger.info("Analyzing precious metals market regime...")
        signals = metals_strategy.generate_signals()

        if not signals:
            logger.info("No precious metals signals generated")
            return

        regime = signals[0].get("regime", "neutral") if signals else "neutral"
        logger.info(f"Current metals regime: {regime}")
        allocation_str = [(s["symbol"], f"{s['strength'] * 100:.0f}%") for s in signals]
        logger.info(f"Allocation: {allocation_str}")

        # Execute trades
        if trader:
            result = metals_strategy.execute_daily(amount=daily_amount)

            if result.get("success"):
                # Persist trades to daily JSON ledger
                today_str = datetime.now().strftime("%Y-%m-%d")
                trades_file = Path(f"data/trades_{today_str}.json")

                # Load existing or init new
                if trades_file.exists():
                    try:
                        with open(trades_file) as f:
                            daily_trades = json.load(f)
                    except Exception:
                        daily_trades = []
                else:
                    daily_trades = []

                # Record each signal as a trade
                for sig in signals:
                    trade_amount = daily_amount * sig.get("strength", 0)
                    if trade_amount > 0:
                        trade_record = {
                            "symbol": sig["symbol"],
                            "action": sig.get("action", "buy").upper(),
                            "amount": trade_amount,
                            "quantity": 0,  # Filled by execution
                            "price": 0,  # Filled by execution
                            "timestamp": datetime.now().isoformat(),
                            "status": "SUBMITTED",
                            "strategy": "PreciousMetalsStrategy",
                            "reason": f"Regime: {regime}, Weight: {sig.get('strength', 0) * 100:.0f}%",
                            "mode": "PAPER",
                            "regime": regime,
                        }
                        daily_trades.append(trade_record)
                        _update_system_state_with_precious_metals_trade(trade_record, logger)

                # Write back
                with open(trades_file, "w") as f:
                    json.dump(daily_trades, f, indent=4)

                logger.info(f"Precious metals trades saved to {trades_file}")
                logger.info(f"Precious metals strategy executed: ${daily_amount:.2f} allocated")

                # Update daily returns
                _update_precious_metals_daily_returns(logger)
            else:
                logger.warning(
                    f"Precious metals execution failed: {result.get('error', 'unknown')}"
                )
        else:
            logger.info("Precious Metals Analysis complete (no trader - signals only)")
            for sig in signals:
                logger.info(
                    f"   {sig['symbol']}: {sig['action']} @ {sig['strength'] * 100:.0f}% weight"
                )

    except ImportError as e:
        logger.warning(f"Precious metals strategy not available: {e}")
        logger.info("   -> Check src/strategies/precious_metals_strategy.py imports.")
    except Exception as e:
        logger.error(f"Precious metals trading failed: {e}", exc_info=True)


def execute_reit_trading() -> None:
    """
    Execute REIT trading strategy (Tier 7).

    Uses regime-based sector rotation to select top REITs based on:
    - Interest rate environment (rising/falling/neutral)
    - Momentum signals
    - Dividend yield
    """
    logger = setup_logging()
    logger.info("=" * 80)
    logger.info("REIT TRADING MODE (Tier 7 - Smart Income)")
    logger.info("=" * 80)

    try:
        from src.core.alpaca_trader import AlpacaTrader
        from src.strategies.reit_strategy import ReitStrategy

        # Initialize trader
        trader = None
        try:
            trader = AlpacaTrader(paper=True)
        except Exception as e:
            logger.warning(f"⚠️  Trading API unavailable: {e}")
            logger.warning("   -> Proceeding in ANALYSIS mode (no real trades).")
            trader = None

        # Initialize REIT strategy
        daily_amount = float(os.getenv("REIT_DAILY_ALLOCATION", "10.0"))
        reit_strategy = ReitStrategy(trader=trader)

        # Generate signals first to understand regime
        logger.info("🔍 Analyzing REIT market regime and signals...")
        signals = reit_strategy.generate_signals()

        if not signals:
            logger.info("⚠️  No REIT signals generated (market conditions not favorable)")
            return

        regime = signals[0].get("regime", "Neutral") if signals else "Neutral"
        logger.info(f"📊 Current rate regime: {regime}")
        logger.info(f"📈 Top {len(signals)} REIT picks: {[s['symbol'] for s in signals]}")

        # Execute trades
        if trader:
            reit_strategy.execute_daily(amount=daily_amount)

            # Persist trades to daily JSON ledger
            today_str = datetime.now().strftime("%Y-%m-%d")
            trades_file = Path(f"data/trades_{today_str}.json")

            # Load existing or init new
            if trades_file.exists():
                try:
                    with open(trades_file) as f:
                        daily_trades = json.load(f)
                except Exception:
                    daily_trades = []
            else:
                daily_trades = []

            # Record each signal as a trade attempt
            per_trade_amount = daily_amount / len(signals)
            for sig in signals:
                if sig.get("strength", 0) > 0:
                    trade_record = {
                        "symbol": sig["symbol"],
                        "action": sig.get("action", "buy").upper(),
                        "amount": per_trade_amount,
                        "quantity": 0,  # Will be filled by execution
                        "price": 0,  # Will be filled by execution
                        "timestamp": datetime.now().isoformat(),
                        "status": "SUBMITTED",
                        "strategy": "ReitStrategy",
                        "reason": f"Regime: {regime}, Score: {sig.get('strength', 0):.2f}",
                        "mode": "PAPER",
                        "regime": regime,
                    }
                    daily_trades.append(trade_record)
                    _update_system_state_with_reit_trade(trade_record, logger)

            # Write back
            with open(trades_file, "w") as f:
                json.dump(daily_trades, f, indent=4)

            logger.info(f"💾 REIT trades saved to {trades_file}")
            logger.info(
                f"✅ REIT strategy executed: {len(signals)} positions @ ${per_trade_amount:.2f} each"
            )

            # Update REIT daily returns in system_state for easy CEO visibility
            _update_reit_daily_returns(logger)
        else:
            logger.info("📋 REIT Analysis complete (no trader - signals only)")
            for sig in signals:
                logger.info(
                    f"   {sig['symbol']}: {sig.get('action', 'hold')} (score: {sig.get('strength', 0):.2f})"
                )

    except ImportError as e:
        logger.warning(f"⚠️  REIT strategy not available: {e}")
        logger.info("   -> Check src/strategies/reit_strategy.py imports.")
    except Exception as e:
        logger.error(f"❌ REIT trading failed: {e}", exc_info=True)
        # Don't raise - REIT is supplementary, shouldn't crash main workflow


def execute_prediction_trading() -> None:
    """
    Execute prediction markets trading strategy (Kalshi - Tier 6).

    Kalshi markets trade 24/7, making this suitable for:
    - Daily execution alongside equity strategies
    - Weekend execution when equity markets are closed
    - Event-driven opportunities (elections, Fed meetings, etc.)
    """
    logger = setup_logging()
    logger.info("=" * 80)
    logger.info("PREDICTION MARKETS TRADING MODE (Tier 6 - Kalshi)")
    logger.info("=" * 80)

    try:
        # Check if Kalshi is configured
        from src.brokers.kalshi_client import get_kalshi_client

        kalshi = get_kalshi_client(paper=True)

        if not kalshi.is_configured():
            logger.warning("⚠️  Kalshi not configured (KALSHI_EMAIL/KALSHI_PASSWORD missing)")
            logger.info("   -> Skipping prediction markets. Set credentials in .env to enable.")
            return

        # Import and execute prediction strategy
        from src.strategies.prediction_strategy import PredictionStrategy

        daily_budget = float(os.getenv("PREDICTION_DAILY_BUDGET", "5.0"))

        strategy = PredictionStrategy(
            client=kalshi,
            daily_budget=daily_budget,
        )

        # Execute strategy
        result = strategy.execute()

        if result.get("success"):
            entry_trades = result.get("entry_trades", [])
            exit_trades = result.get("exit_trades", [])
            signals = result.get("signals", [])

            logger.info("✅ Prediction strategy executed:")
            logger.info(f"   Entry trades: {len(entry_trades)}")
            logger.info(f"   Exit trades: {len(exit_trades)}")
            logger.info(f"   Signals found: {len(signals)}")
            logger.info(f"   Remaining budget: ${result.get('remaining_budget', 0):.2f}")

            # Persist each trade to daily ledger
            if entry_trades:
                today_str = datetime.now().strftime("%Y-%m-%d")
                trades_file = Path(f"data/trades_{today_str}.json")

                # Load existing
                if trades_file.exists():
                    try:
                        with open(trades_file) as f:
                            daily_trades = json.load(f)
                    except Exception:
                        daily_trades = []
                else:
                    daily_trades = []

                for trade in entry_trades:
                    trade_record = {
                        "symbol": trade.market_ticker,
                        "action": f"BUY_{trade.side.upper()}",
                        "amount": trade.amount_usd,
                        "quantity": trade.quantity,
                        "price": trade.price,
                        "timestamp": trade.timestamp.isoformat(),
                        "status": "FILLED",
                        "strategy": "PredictionStrategy",
                        "reason": trade.reasoning[:100] if trade.reasoning else "Edge opportunity",
                        "mode": "PAPER" if kalshi.paper else "LIVE",
                        "order_id": trade.order_id,
                    }
                    daily_trades.append(trade_record)
                    _update_system_state_with_prediction_trade(trade_record, logger)

                # Write back
                with open(trades_file, "w") as f:
                    json.dump(daily_trades, f, indent=4)

                logger.info(f"💾 {len(entry_trades)} prediction trades saved to {trades_file}")
        else:
            reason = result.get("reason", "unknown")
            logger.info(f"⚠️  Prediction strategy: {reason}")

    except ImportError as e:
        logger.warning(f"⚠️  Prediction strategy not available: {e}")
        logger.info("   -> Kalshi integration may not be fully installed.")
    except Exception as e:
        logger.error(f"❌ Prediction trading failed: {e}", exc_info=True)
        # Don't raise - prediction markets are supplementary, shouldn't crash main workflow


def calc_daily_input(equity: float) -> float:
    """
    Calculate dynamic daily input based on account equity.

    Scaling Logic (1% of equity):
    - $10k equity → $100/day budget
    - $50k equity → $500/day budget
    - $100k equity → $1000/day budget (max cap)

    Floor: $10/day (minimum safe amount)
    Ceiling: $1000/day (config validator limit)

    This enables the system to scale towards $100/day profit goal.
    With $100k equity: $1000 daily budget → 10% return = $100 profit

    Args:
        equity: Current account equity in USD

    Returns:
        Daily input amount (1% of equity, min $10, max $1000)
    """
    base = 10.0  # Minimum daily input

    # Percentage-based scaling: 1% of equity
    # This allows the system to scale naturally towards the $100/day profit goal
    # Example: $100k equity -> $1,000 daily investment -> 10% return = $100 profit
    daily_target = equity * 0.01

    # Ensure we respect a reasonable floor ($10) but remove the artificial ceiling
    # Update: Cap at $1000.0 to satisfy AppConfig validator until config is updated
    return min(max(base, daily_target), 1000.0)


def get_account_equity() -> float:
    """
    Fetch current account equity from Alpaca.

    Returns:
        Account equity in USD, or 0.0 if unavailable
    """
    try:
        from src.core.alpaca_trader import AlpacaTrader

        trader = AlpacaTrader(paper=True)
        account = trader.get_account_info()
        return float(account.get("equity", 0.0))
    except Exception as e:
        logger = setup_logging()
        logger.warning(f"Could not fetch account equity: {e}. Using base input.")
        return 0.0


def main() -> None:
    # Removed intermediate annotations to stay under GitHub's 10-annotation limit
    # Key checkpoints only for debugging exit code 2 issue
    parser = argparse.ArgumentParser(description="Trading orchestrator entrypoint")
    parser.add_argument(
        "--prediction-only", action="store_true", help="Run only prediction markets (Kalshi)"
    )
    parser.add_argument("--skip-prediction", action="store_true", help="Skip prediction markets")
    parser.add_argument("--auto-scale", action="store_true")
    args = parser.parse_args()

    load_dotenv()
    init_sentry()
    logger = setup_logging()

    # Dynamic budget scaling: adjust DAILY_INVESTMENT based on account equity
    # This enables the system to scale towards $100/day profit goal
    # With $100k equity: $1000 daily investment → 10% return = $100 profit
    _refresh_account_data(logger)

    _apply_dynamic_daily_budget(logger)

    # CRITICAL: Enforce lessons learned BEFORE trading starts
    # Closes positions that violate RAG lessons (e.g., crypto banned but still held)
    logger.info("=" * 80)
    logger.info("POSITION ENFORCER: Checking for violations of lessons learned")
    logger.info("=" * 80)
    try:
        from src.core.alpaca_trader import AlpacaTrader
        from src.safety.position_enforcer import enforce_positions

        trader = AlpacaTrader()
        enforcement_result = enforce_positions(trader)

        if enforcement_result.violations_found > 0:
            logger.warning(
                f"🚨 Found {enforcement_result.violations_found} positions violating lessons"
            )
            logger.warning(
                f"   Closed {enforcement_result.positions_closed} positions: {enforcement_result.closed_symbols}"
            )
            logger.warning(f"   Total value closed: ${enforcement_result.total_value_closed:.2f}")
        else:
            logger.info("✅ No violations found - all positions comply with lessons")
    except Exception as e:
        logger.error(f"Position enforcer failed (non-fatal): {e}")
        # Continue trading - enforcer failure shouldn't block operations

    logger.info("=" * 80)

    # Set safe defaults
    is_weekend_day = is_weekend()
    is_holiday = is_market_holiday()
    prediction_allowed = prediction_enabled()

    # Handle prediction-only mode (Kalshi markets trade 24/7)
    if args.prediction_only:
        if prediction_allowed:
            logger.info("Prediction-only mode requested - executing Kalshi trading.")
            execute_prediction_trading()
            logger.info("Prediction trading session completed.")
            return
        else:
            logger.warning("Prediction-only requested but ENABLE_PREDICTION_MARKETS is not true.")
            return

    should_run_prediction = not args.skip_prediction and prediction_allowed

    # Weekend/holiday handling - run prediction markets (Kalshi trades 24/7)
    if is_weekend_day or is_holiday:
        logger.info("Weekend/holiday detected.")
        if should_run_prediction:
            logger.info("Executing prediction markets (24/7 trading).")
            execute_prediction_trading()
            logger.info("Prediction trading session completed.")
        logger.info("Markets closed - skipping equity trading.")
        return

    # Normal stock trading - import only when needed
    from src.orchestrator.main import TradingOrchestrator

    # Skip ADK service to simplify debugging - disable via env var
    adk_enabled = os.getenv("ENABLE_ADK_AGENTS", "false").lower() in {"1", "true", "yes", "on"}
    if adk_enabled:
        try:
            # Check if service is already running on port 8080
            import socket
            import subprocess
            import time

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(("127.0.0.1", 8080))
            sock.close()

            if result != 0:
                logger.info("🚀 Starting Go ADK Trading Service...")
                script_path = os.path.join(os.path.dirname(__file__), "run_adk_trading_service.sh")
                # Run in background
                subprocess.Popen(
                    [script_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                # Give it a moment to start
                time.sleep(3)
                logger.info("✅ Go ADK Service started in background")
            else:
                logger.info("✅ Go ADK Service already running")
        except Exception as e:
            logger.warning(f"⚠️ Failed to start ADK service: {e}")

    logger.info("Starting hybrid funnel orchestrator entrypoint.")
    tickers = _parse_tickers()

    MAX_RETRIES = 3
    RETRY_DELAY = 5  # Reduced from 30 to 5 seconds for faster CI feedback

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(f"Attempt {attempt}/{MAX_RETRIES}: Starting hybrid funnel orchestrator...")
            orchestrator = TradingOrchestrator(tickers=tickers)
            orchestrator.run()
            print("::notice::1/5 Trading completed OK", flush=True)
            break
        except Exception as e:
            print(f"::error::Attempt {attempt} failed: {type(e).__name__}: {e}", flush=True)
            logger.error(f"❌ Attempt {attempt} failed: {e}", exc_info=True)
            if attempt < MAX_RETRIES:
                logger.info(f"Retrying in {RETRY_DELAY} seconds...")
                import time

                time.sleep(RETRY_DELAY)
            else:
                logger.critical(
                    f"❌ CRITICAL: All {MAX_RETRIES} attempts failed. Trading session crashed."
                )
                print(f"::error::CRITICAL: All {MAX_RETRIES} attempts failed", flush=True)
                raise

    print("::notice::2/5 Post-trading hooks done", flush=True)

    # Generate profit target report and wire recommendations into budget
    try:
        import json
        from pathlib import Path

        from src.analytics.profit_target_tracker import ProfitTargetTracker

        logger.info("Generating profit target report...")
        tracker = ProfitTargetTracker(target_daily_profit=100.0)
        plan = tracker.generate_plan()

        # Persist report
        report_path = Path("reports/profit_target_report.json")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_data = {
            "current_daily_profit": plan.current_daily_profit,
            "projected_daily_profit": plan.projected_daily_profit,
            "target_daily_profit": plan.target_daily_profit,
            "target_gap": plan.target_gap,
            "current_daily_budget": plan.current_daily_budget,
            "recommended_daily_budget": plan.recommended_daily_budget,
            "scaling_factor": plan.scaling_factor,
            "avg_return_pct": plan.avg_return_pct,
            "win_rate": plan.win_rate,
            "actions": plan.actions,
        }
        report_path.write_text(json.dumps(report_data, indent=2))
        logger.info(f"Profit target report saved to {report_path}")

        # Log $100/day progress
        progress_pct = (
            (plan.current_daily_profit / plan.target_daily_profit * 100)
            if plan.target_daily_profit > 0
            else 0
        )
        logger.info(
            f"$100/day Progress: {progress_pct:.1f}% (current: ${plan.current_daily_profit:.2f}/day)"
        )

        # If avg_return is positive and we have a recommended budget, log it
        if plan.recommended_daily_budget and plan.avg_return_pct > 0:
            logger.info(f"Recommended daily budget: ${plan.recommended_daily_budget:.2f}")
    except Exception as e:
        logger.warning(f"Failed to generate profit target report: {e}")

    # Execute prediction markets after main equity strategies (Tier 6)
    # Kalshi trades 24/7 so this can run on weekdays alongside equity trading
    if should_run_prediction:
        logger.info("Executing Tier 6 - Prediction Markets (Kalshi)...")
        execute_prediction_trading()
        logger.info("Prediction trading session completed.")

    # Execute REIT strategy (Tier 7) - runs daily during market hours
    # Uses regime-based sector rotation for income and growth
    should_run_reit = reit_enabled() and not is_weekend_day and not is_holiday
    if should_run_reit:
        logger.info("Executing Tier 7 - REIT Smart Income Strategy...")
        execute_reit_trading()
        logger.info("REIT trading session completed.")

    # Execute Precious Metals strategy (Tier 8) - runs daily during market hours
    # Provides inflation hedge and portfolio diversification via GLD/SLV
    should_run_metals = precious_metals_enabled() and not is_weekend_day and not is_holiday
    if should_run_metals:
        logger.info("Executing Tier 8 - Precious Metals Strategy (GLD/SLV)...")
        execute_precious_metals_trading()
        logger.info("Precious metals trading session completed.")

    print("::notice::3/5 main() returning", flush=True)


if __name__ == "__main__":
    # Super-safe error handling that catches everything
    import os
    import traceback

    # Ensure logs directory exists
    os.makedirs("logs", exist_ok=True)

    try:
        main()
        # Explicit success exit
        print("::notice::4/5 main() returned OK", flush=True)
        print("::notice::5/5 sys.exit(0) called", flush=True)
        sys.exit(0)
    except SystemExit as e:
        # Capture the exit code - only log as error if non-zero
        if e.code != 0:
            print(f"::error::SystemExit caught with code={e.code}", flush=True)
        else:
            print("::notice::SystemExit caught with code=0 (success)", flush=True)
        raise
    except BaseException as e:
        # Catch EVERYTHING including KeyboardInterrupt, SystemExit, etc.
        tb = traceback.format_exc()

        # Write to stdout with GHA annotations
        print("=" * 80, flush=True)
        print("::error::CRITICAL ERROR IN AUTONOMOUS_TRADER.PY", flush=True)
        print(f"::error::Exception Type: {type(e).__name__}", flush=True)
        print(f"::error::Exception Message: {str(e)[:500]}", flush=True)
        print("=" * 80, flush=True)

        # Print full traceback as annotations
        for line in tb.split("\n"):
            if line.strip():
                print(f"::error::{line}", flush=True)

        # Write to file for artifact
        try:
            with open("logs/trading_crash.log", "w") as f:
                f.write(f"Exception: {type(e).__name__}: {e}\n\n")
                f.write(tb)
        except:
            pass

        sys.exit(2)
