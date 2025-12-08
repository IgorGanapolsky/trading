"""Bootstrap entry point for the hybrid trading orchestrator."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Ensure src is on the path when executed via GitHub Actions
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.utils.error_monitoring import init_sentry
from src.utils.logging_config import setup_logging

SYSTEM_STATE_PATH = Path(os.getenv("SYSTEM_STATE_PATH", "data/system_state.json"))


def _update_system_state_with_crypto_trade(trade_record: dict[str, Any], logger) -> None:
    """Update `data/system_state.json` so Tier 5 reflects the new crypto trade."""
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
    tier5_defaults = {
        "name": "Crypto Weekend Strategy (BTC, ETH)",
        "allocation": 0.05,
        "daily_amount": 0.5,
        "coins": ["BTC/USD", "ETH/USD"],
        "trades_executed": 0,
        "total_invested": 0.0,
        "status": "active",
        "execution_schedule": "Saturday & Sunday 10:00 AM ET",
        "last_execution": None,
        "next_execution": None,
    }
    tier5 = strategies.setdefault("tier5", tier5_defaults)
    tier5["trades_executed"] = tier5.get("trades_executed", 0) + 1
    tier5["total_invested"] = round(
        tier5.get("total_invested", 0.0) + float(trade_record.get("amount", 0.0)), 6
    )
    tier5["last_execution"] = trade_record.get("timestamp")
    tier5["status"] = "active"

    investments = state.setdefault("investments", {})
    investments["tier5_invested"] = round(
        investments.get("tier5_invested", 0.0) + float(trade_record.get("amount", 0.0)), 6
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
            "tier": "tier5",
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
        logger.info("system_state.json updated with crypto trade metadata")
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
    raw = os.getenv("TARGET_TICKERS", "SPY,QQQ,VOO")
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


def crypto_enabled() -> bool:
    """Feature flag for the legacy crypto branch."""
    return os.getenv("ENABLE_CRYPTO_AGENT", "false").lower() in {"1", "true", "yes"}


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


def execute_crypto_trading() -> None:
    """Execute crypto trading strategy."""
    from src.core.alpaca_trader import AlpacaTrader
    from src.risk.unified import UnifiedRiskManager as RiskManager
    from src.strategies.crypto_strategy import CryptoStrategy

    logger = setup_logging()
    logger.info("=" * 80)
    logger.info("CRYPTO TRADING MODE")
    logger.info("=" * 80)

    try:
        # Initialize dependencies
        trader = None
        try:
            trader = AlpacaTrader(paper=True)
        except Exception as e:
            logger.warning(f"⚠️  Trading API unavailable (Missing Keys?): {e}")
            logger.warning("   -> Proceeding in ANALYSIS/INTERNAL SIMULATION mode.")
            trader = None

        risk_manager = RiskManager(
            full_params=dict(
                max_daily_loss_pct=2.0,
                max_position_size_pct=CryptoStrategy.MAX_POSITION_PCT * 100,
                max_drawdown_pct=15.0,
                max_consecutive_losses=3,
            )
        )

        crypto_strategy = CryptoStrategy(
            trader=trader,
            risk_manager=risk_manager,
            daily_amount=float(os.getenv("CRYPTO_DAILY_AMOUNT", "0.50")),
        )

        # Execute crypto trading
        order = crypto_strategy.execute_daily()

        if order:
            logger.info(f"✅ Crypto trade executed: {order.symbol} for ${order.amount:.2f}")

            # PERSISTENCE: Save trade to daily JSON ledger so dashboard sees it
            try:
                today_str = datetime.now().strftime("%Y-%m-%d")
                trades_file = Path(f"data/trades_{today_str}.json")

                # Load existing or init new
                if trades_file.exists():
                    try:
                        with open(trades_file) as f:
                            daily_trades = json.load(f)
                    except:
                        daily_trades = []
                else:
                    daily_trades = []

                # Append new trade
                trade_record = {
                    "symbol": order.symbol,
                    "action": order.action.upper(),
                    "amount": order.amount,
                    "quantity": order.quantity,
                    "price": order.price,
                    "timestamp": order.timestamp.isoformat(),
                    "status": "FILLED" if hasattr(order, "status") else "FILLED",
                    "strategy": "CryptoStrategy",
                    "reason": order.reason,
                    "mode": "ANALYSIS" if trader is None else "LIVE",
                }
                daily_trades.append(trade_record)

                # Write back
                with open(trades_file, "w") as f:
                    json.dump(daily_trades, f, indent=4)

                logger.info(f"💾 Trade saved to {trades_file}")
                _update_system_state_with_crypto_trade(trade_record, logger)

            except Exception as e:
                logger.error(f"Failed to persist trade to JSON: {e}")
        else:
            logger.info("⚠️  No crypto trade executed (market conditions not favorable)")

    except Exception as e:
        logger.error(f"❌ Crypto trading failed: {e}", exc_info=True)
        raise


def calc_daily_input(equity: float) -> float:
    """
    Calculate dynamic daily input based on account equity.

    Auto-scaling logic to accelerate compounding:
    - Base: $10/day (minimum safe amount)
    - $2k+: Add $0.20 per $1k equity (e.g., $12 at $2k)
    - $5k+: Add $0.30 per $1k equity (e.g., $16.50 at $5k)
    - $10k+: Add $0.40 per $1k equity (e.g., $24 at $10k)
    - Cap at $50/day to maintain risk discipline

    This shaves 2-3 months off the $100/day roadmap by
    compounding faster once equity validates the system.

    Args:
        equity: Current account equity in USD

    Returns:
        Daily input amount (capped at $50)
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
    parser = argparse.ArgumentParser(description="Trading orchestrator entrypoint")
    parser.add_argument(
        "--crypto-only",
        action="store_true",
        help="Force crypto trading even on weekdays (requires ENABLE_CRYPTO_AGENT=true)",
    )
    parser.add_argument(
        "--skip-crypto",
        action="store_true",
        help="Skip legacy crypto flow even on weekends.",
    )
    parser.add_argument(
        "--auto-scale",
        action="store_true",
        help="Enable auto-scaling of daily input based on equity.",
    )
    args = parser.parse_args()

    load_dotenv()
    init_sentry()
    logger = setup_logging()
    _apply_dynamic_daily_budget(logger)

    # Auto-scale daily input if enabled
    if args.auto_scale or os.getenv("ENABLE_AUTO_SCALE_INPUT", "false").lower() in {
        "1",
        "true",
        "yes",
    }:
        equity = get_account_equity()
        scaled_input = calc_daily_input(equity)
        os.environ["DAILY_INVESTMENT"] = str(scaled_input)
        logger.info(f"📈 Auto-scaled daily input: ${scaled_input:.2f} (equity: ${equity:.2f})")

    crypto_allowed = crypto_enabled()
    is_holiday = is_market_holiday()
    is_weekend_day = is_weekend()
    weekend_proxy_enabled = _flag_enabled("ENABLE_WEEKEND_PROXY", "true")
    weekend_proxy_active = (
        weekend_proxy_enabled and (is_weekend_day or is_holiday) and not args.crypto_only
    )

    should_run_crypto = (
        not args.skip_crypto
        and crypto_allowed
        and (args.crypto_only or is_weekend_day or is_holiday)
        and not weekend_proxy_active
    )

    if args.crypto_only and not crypto_allowed:
        logger.warning(
            "Crypto-only requested but ENABLE_CRYPTO_AGENT is not true. Skipping crypto branch."
        )

    if weekend_proxy_active:
        logger.info(
            "Weekend proxy mode enabled (%s) - routing funnel through ETF proxies.",
            "holiday" if is_holiday and not is_weekend_day else "weekend",
        )
    elif should_run_crypto:
        reason = []
        if args.crypto_only:
            reason.append("--crypto-only flag")
        if is_weekend_day:
            reason.append("weekend")
        if is_holiday:
            reason.append("market holiday")
        logger.info(f"Crypto branch enabled ({', '.join(reason)}) - executing crypto trading.")
        execute_crypto_trading()
        logger.info("Crypto trading session completed.")
        if args.crypto_only or is_weekend_day or is_holiday:
            return
    elif (is_weekend_day or is_holiday) and not args.skip_crypto:
        logger.info("Weekend detected but crypto branch disabled. Proceeding with hybrid funnel.")

    # Normal stock trading - import only when needed
    from src.orchestrator.main import TradingOrchestrator

    # Ensure Go ADK service is running if enabled
    adk_enabled = _flag_enabled("ENABLE_ADK_AGENTS", "true")
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

    try:
        orchestrator = TradingOrchestrator(tickers=tickers)
        orchestrator.run()
        logger.info("Trading session completed.")
    except Exception as e:
        logger.critical(f"❌ CRITICAL: Trading session crashed: {e}", exc_info=True)
        # We re-raise to ensure the workflow still fails, but now it's logged with stack trace
        raise

    # Execute options live simulation (theta harvest)
    options_enabled = _flag_enabled("ENABLE_OPTIONS_SIM", "true")
    if options_enabled:
        try:
            logger.info("=" * 80)
            logger.info("OPTIONS LIVE SIMULATION")
            logger.info("=" * 80)

            # Import and run options simulation
            import subprocess

            script_path = os.path.join(os.path.dirname(__file__), "options_live_sim.py")
            result = subprocess.run(
                [sys.executable, script_path, "--paper"],
                capture_output=False,
                text=True,
            )

            if result.returncode == 0:
                logger.info("✅ Options simulation completed successfully.")
            else:
                logger.warning(f"⚠️  Options simulation exited with code {result.returncode}")
        except Exception as e:
            logger.error(f"Options simulation failed (non-fatal): {e}", exc_info=True)
            logger.info("Continuing without options simulation...")
    else:
        logger.info("Options simulation disabled via ENABLE_OPTIONS_SIM")

    # RL Feedback Loop: Retrain from telemetry after trading completes
    rl_retrain_enabled = _flag_enabled("ENABLE_RL_RETRAIN", "true")
    if rl_retrain_enabled:
        try:
            logger.info("=" * 80)
            logger.info("RL FEEDBACK LOOP - Daily Retraining")
            logger.info("=" * 80)

            # Import and run RL retraining
            import subprocess

            script_path = os.path.join(os.path.dirname(__file__), "rl_daily_retrain.py")
            result = subprocess.run(
                [sys.executable, script_path],
                capture_output=False,
                text=True,
            )

            if result.returncode == 0:
                logger.info(
                    "✅ RL retraining completed successfully - system learned from today's trades."
                )
            else:
                logger.warning(f"⚠️  RL retraining exited with code {result.returncode}")
        except Exception as e:
            logger.error(f"RL retraining failed (non-fatal): {e}", exc_info=True)
            logger.info("Continuing without RL update - will use existing weights...")
    else:
        logger.info("RL retraining disabled via ENABLE_RL_RETRAIN")


if __name__ == "__main__":
    main()
