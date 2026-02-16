#!/usr/bin/env python3
"""
Sync Alpaca State - Refresh local data from live broker.

Created: Dec 28, 2025
Purpose: Prevent stale data by syncing from Alpaca before trading.

This script:
1. Fetches current account state from Alpaca
2. Updates data/system_state.json with fresh data
3. Returns non-zero exit code on failure

Run automatically via:
- .github/workflows/pre-market-sync.yml (scheduled)
- Session start hook (on-demand)
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

SYSTEM_STATE_FILE = PROJECT_ROOT / "data" / "system_state.json"
REQUIRE_KEYS_ENV = "REQUIRE_ALPACA_KEYS"


class AlpacaSyncError(Exception):
    """Raised when Alpaca sync fails - NEVER fall back to simulated data."""

    pass


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_filled_at(raw_value: str | None) -> datetime | None:
    """Best-effort timestamp parser for Alpaca filled_at strings."""
    if not raw_value:
        return None
    raw = str(raw_value).strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def sync_from_alpaca() -> dict | None:
    """
    Sync account state from Alpaca.

    Returns:
        Dict with REAL account data from Alpaca (both PAPER and LIVE).

    Raises:
        AlpacaSyncError: If API keys missing or connection fails.
                         NEVER returns simulated/fake data.
    """
    logger.info("🔄 Syncing from Alpaca...")

    # Check for API keys - FAIL LOUDLY if missing
    from src.utils.alpaca_client import get_alpaca_credentials

    api_key, api_secret = get_alpaca_credentials()

    if not api_key or not api_secret:
        # Strict mode for CI/automation: fail loudly if keys are required.
        if _truthy(os.getenv(REQUIRE_KEYS_ENV)):
            raise AlpacaSyncError(
                f"Missing Alpaca credentials while {REQUIRE_KEYS_ENV}=true. "
                "Refusing stale-data sync."
            )

        logger.warning("⚠️ No Alpaca API keys found - preserving existing data")
        # DO NOT overwrite real data with simulated values.
        # Return None to signal timestamp-only update.
        return None

    result = {"paper": None, "live": None}

    # ========== SYNC PAPER ACCOUNT ==========
    try:
        from src.execution.alpaca_executor import AlpacaExecutor

        executor = AlpacaExecutor(paper=True, allow_simulator=False)
        executor.sync_portfolio_state()

        positions = executor.get_positions()
        last_equity = executor.account_snapshot.get("last_equity")
        try:
            daily_change = float(executor.account_equity) - float(last_equity)
        except (TypeError, ValueError):
            daily_change = 0.0

        # LL-237: Fetch trade history from closed orders to prevent knowledge loss
        trade_history = []
        try:
            from alpaca.trading.enums import QueryOrderStatus
            from alpaca.trading.requests import GetOrdersRequest

            try:
                orders = executor.client.get_orders(
                    filter=GetOrdersRequest(status=QueryOrderStatus.CLOSED, limit=200, nested=True)
                )
            except TypeError:
                # Backward compatibility with older alpaca-py request schema.
                orders = executor.client.get_orders(
                    filter=GetOrdersRequest(status=QueryOrderStatus.CLOSED, limit=200)
                )

            trade_history = []
            for o in orders:
                if not o.filled_at:
                    continue
                raw_legs = getattr(o, "legs", None) or []
                leg_symbols = []
                for leg in raw_legs:
                    if isinstance(leg, dict):
                        leg_symbol = leg.get("symbol")
                    else:
                        leg_symbol = getattr(leg, "symbol", None)
                    if leg_symbol:
                        leg_symbols.append(str(leg_symbol))

                trade_history.append(
                    {
                        "id": str(getattr(o, "id", "")),
                        "symbol": getattr(o, "symbol", None),
                        "side": str(getattr(o, "side", "")),
                        "qty": str(getattr(o, "filled_qty", 0)),
                        "price": str(getattr(o, "filled_avg_price", 0) or "0"),
                        "filled_at": str(getattr(o, "filled_at", "")),
                        "status": str(getattr(o, "status", "")),
                        "order_class": str(getattr(o, "order_class", "")),
                        "legs": leg_symbols,
                    }
                )
            logger.info(f"📜 Fetched {len(trade_history)} closed trades from PAPER history")
        except Exception as e:
            logger.warning(f"⚠️ Could not fetch PAPER trade history: {e}")

        result["paper"] = {
            "equity": executor.account_equity,
            "cash": executor.account_snapshot.get("cash", 0),
            "buying_power": executor.account_snapshot.get("buying_power", 0),
            "positions": positions,
            "positions_count": len(positions),
            "trade_history": trade_history,
            "trades_loaded": len(trade_history),
            "daily_change": round(daily_change, 2),
            "mode": "paper",
            "synced_at": datetime.now().isoformat(),
        }
        logger.info(f"✅ PAPER account synced: ${executor.account_equity:,.2f}")

    except Exception as e:
        logger.error(f"❌ Failed to sync PAPER account: {e}")

    # ========== SYNC LIVE (BROKERAGE) ACCOUNT ==========
    # LL-281: Dashboard was showing PAPER data for LIVE account because we never fetched LIVE
    live_api_key = os.environ.get("ALPACA_BROKERAGE_TRADING_API_KEY")
    live_api_secret = os.environ.get("ALPACA_BROKERAGE_TRADING_API_SECRET")

    if live_api_key and live_api_secret:
        try:
            from alpaca.trading.client import TradingClient

            live_client = TradingClient(live_api_key, live_api_secret, paper=False)
            live_account = live_client.get_account()

            result["live"] = {
                "equity": float(live_account.equity),
                "cash": float(live_account.cash),
                "buying_power": float(live_account.buying_power),
                "positions_count": 0,  # Can add position fetch later
                "mode": "live",
                "synced_at": datetime.now().isoformat(),
            }
            logger.info(f"✅ LIVE account synced: ${float(live_account.equity):,.2f}")

        except Exception as e:
            logger.warning(f"⚠️ Could not sync LIVE account: {e}")
            # Don't fail - LIVE account sync is optional
    else:
        logger.info("ℹ️ No LIVE account credentials - skipping LIVE sync")

    # Return combined result
    if result["paper"] is None and result["live"] is None:
        raise AlpacaSyncError("Failed to sync both PAPER and LIVE accounts")

    return result


def update_system_state(alpaca_data: dict | None) -> None:
    """
    Update system_state.json with fresh Alpaca data.

    If alpaca_data is None, only update timestamp (preserve existing values).
    Now handles both PAPER and LIVE accounts separately (LL-281 fix).
    """
    logger.info("📝 Updating system_state.json...")

    # Load existing state
    if SYSTEM_STATE_FILE.exists():
        with open(SYSTEM_STATE_FILE) as f:
            state = json.load(f)
    else:
        state = {}

    # Update meta timestamp regardless
    state.setdefault("meta", {})
    state.setdefault("sync_health", {})
    now_iso = _now_utc_iso()
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    state["meta"]["last_updated"] = now_iso
    state["meta"]["last_sync_attempt"] = now_iso
    state["last_updated"] = now_iso

    if alpaca_data is None:
        # No API keys - only update timestamp, preserve existing data
        state["meta"]["last_sync"] = now_iso
        state["meta"]["sync_mode"] = "skipped_no_keys"
        state["meta"]["alpaca_keys_present"] = False
        state["sync_health"]["last_attempt"] = now_iso
        state["sync_health"]["sync_source"] = "sync_alpaca_state.py"
        logger.info("⚠️ No API keys - preserving existing account values, only updating timestamp")
    else:
        # LL-281: Handle new structure with separate PAPER and LIVE data
        paper_data = alpaca_data.get("paper")
        live_data = alpaca_data.get("live")
        state["meta"]["alpaca_keys_present"] = True

        # ========== UPDATE PAPER ACCOUNT ==========
        if paper_data:
            # CRITICAL: Reject simulated data
            mode = paper_data.get("mode", "unknown")
            if mode == "simulated":
                raise AlpacaSyncError(f"REFUSING to update with SIMULATED data! mode='{mode}'")

            # Update account section (primary account = PAPER for R&D)
            state.setdefault("account", {})
            state["account"]["current_equity"] = paper_data.get("equity", 0)
            state["account"]["cash"] = paper_data.get("cash", 0)
            state["account"]["buying_power"] = paper_data.get("buying_power", 0)
            state["account"]["positions_count"] = paper_data.get("positions_count", 0)

            # Calculate P/L for PAPER
            paper_starting = state.get("paper_account", {}).get("starting_balance", 5000.0)
            paper_current = paper_data.get("equity", 0)
            state["account"]["total_pl"] = paper_current - paper_starting
            state["account"]["total_pl_pct"] = (
                ((paper_current - paper_starting) / paper_starting) * 100
                if paper_starting > 0
                else 0
            )

            # Update paper_account section
            state.setdefault("paper_account", {})
            state["paper_account"]["current_equity"] = paper_data.get("equity", 0)
            state["paper_account"]["equity"] = paper_data.get("equity", 0)
            state["paper_account"]["cash"] = paper_data.get("cash", 0)
            state["paper_account"]["buying_power"] = paper_data.get("buying_power", 0)
            state["paper_account"]["positions_count"] = paper_data.get("positions_count", 0)
            state["paper_account"]["starting_balance"] = paper_starting
            state["paper_account"]["total_pl"] = paper_current - paper_starting
            state["paper_account"]["total_pl_pct"] = (
                ((paper_current - paper_starting) / paper_starting) * 100
                if paper_starting > 0
                else 0
            )
            state["paper_account"]["daily_change"] = paper_data.get("daily_change", 0.0)

            # Update meta
            state["meta"]["last_sync"] = paper_data.get("synced_at") or now_iso

            # Store positions in performance.open_positions
            positions = paper_data.get("positions", [])
            mapped_positions = [
                {
                    "symbol": p.get("symbol"),
                    "quantity": p.get("qty") or p.get("quantity", 0),
                    "entry_price": p.get("avg_entry_price", 0),
                    "current_price": p.get("current_price", 0),
                    "market_value": p.get("market_value", 0),
                    "unrealized_pl": p.get("unrealized_pl", 0),
                    "unrealized_pl_pct": p.get("unrealized_plpc", 0),
                    "side": p.get("side", "long"),
                }
                for p in positions
                if p.get("symbol")
            ]
            state.setdefault("performance", {})
            state["performance"]["open_positions"] = mapped_positions
            state["account"]["positions_count"] = len(mapped_positions)
            state["paper_account"]["positions_count"] = len(mapped_positions)

            # Legacy compatibility fields consumed by dashboards/docs.
            state.setdefault("portfolio", {})
            state["portfolio"]["equity"] = paper_data.get("equity", 0)
            state["portfolio"]["cash"] = paper_data.get("cash", 0)
            state["positions"] = [
                {
                    "symbol": p.get("symbol"),
                    "qty": p.get("qty") or p.get("quantity", 0),
                    "price": p.get("current_price", 0),
                    "value": p.get("market_value", 0),
                    "pnl": p.get("unrealized_pl", 0),
                    "type": "option" if len(str(p.get("symbol", ""))) > 10 else "stock",
                }
                for p in positions
                if p.get("symbol")
            ]

            unrealized_total = sum(float(p.get("unrealized_pl", 0) or 0) for p in positions)
            state.setdefault("risk", {})
            state["risk"]["total_pl"] = state["account"]["total_pl"]
            state["risk"]["unrealized_pl"] = round(unrealized_total, 2)
            state["risk"]["status"] = (
                "MONITORING" if state["account"]["total_pl"] >= 0 else "WARNING - NEGATIVE P/L"
            )

            # Sync trade_history
            trade_history = paper_data.get("trade_history", [])
            if trade_history:
                state["trade_history"] = trade_history
                state["trades_loaded"] = len(trade_history)
                logger.info(f"📜 Recorded {len(trade_history)} trades to history")
            else:
                existing_history = state.get("trade_history", [])
                if existing_history:
                    logger.info(f"📜 Preserved {len(existing_history)} existing trades")

            # Keep a lightweight trade summary for existing dashboards.
            todays_fills = 0
            last_trade_dt: datetime | None = None
            last_trade_symbol: str | None = None
            for trade in state.get("trade_history", []):
                filled_at = str(trade.get("filled_at") or "")
                filled_dt = _parse_filled_at(filled_at)
                if filled_at.startswith(today_str):
                    todays_fills += 1
                if filled_dt and (last_trade_dt is None or filled_dt > last_trade_dt):
                    last_trade_dt = filled_dt
                    symbol = trade.get("symbol")
                    if symbol not in (None, "", "None"):
                        last_trade_symbol = str(symbol)

            if last_trade_symbol is None and state.get("trade_history"):
                # Fallback to newest non-null symbol if most recent fill had no symbol.
                symbol_candidates = []
                for trade in state.get("trade_history", []):
                    symbol = trade.get("symbol")
                    if symbol in (None, "", "None"):
                        continue
                    filled_dt = _parse_filled_at(str(trade.get("filled_at") or ""))
                    if filled_dt:
                        symbol_candidates.append((filled_dt, str(symbol)))
                if symbol_candidates:
                    last_trade_symbol = max(symbol_candidates, key=lambda pair: pair[0])[1]

            state["trades"] = {
                "last_trade_date": last_trade_dt.date().isoformat() if last_trade_dt else None,
                "today_trades": todays_fills,
                "total_trades_today": todays_fills,
                "last_trade_symbol": last_trade_symbol,
            }

        # ========== UPDATE LIVE (BROKERAGE) ACCOUNT ==========
        # LL-281: This was MISSING - dashboard showed PAPER data for LIVE
        if live_data:
            state.setdefault("live_account", {})
            live_starting = state["live_account"].get("starting_balance", 20.0)
            live_current = live_data.get("equity", 0)

            state["live_account"]["current_equity"] = live_current
            state["live_account"]["equity"] = live_current
            state["live_account"]["cash"] = live_data.get("cash", 0)
            state["live_account"]["buying_power"] = live_data.get("buying_power", 0)
            state["live_account"]["positions_count"] = live_data.get("positions_count", 0)
            state["live_account"]["starting_balance"] = live_starting
            state["live_account"]["total_pl"] = live_current - live_starting
            state["live_account"]["total_pl_pct"] = (
                ((live_current - live_starting) / live_starting) * 100 if live_starting > 0 else 0
            )
            state["live_account"]["synced_at"] = live_data.get("synced_at")

            logger.info(f"✅ LIVE account stored: ${live_current:,.2f}")
        else:
            # Preserve existing live_account data if we didn't fetch new
            if "live_account" not in state:
                state["live_account"] = {
                    "current_equity": 20.0,
                    "equity": 20.0,
                    "starting_balance": 20.0,
                    "total_pl": 0.0,
                    "total_pl_pct": 0.0,
                    "note": "LIVE account not synced - building capital via deposits",
                }

        if paper_data and live_data:
            state["meta"]["sync_mode"] = "paper+live"
        elif paper_data:
            state["meta"]["sync_mode"] = "paper"
        elif live_data:
            state["meta"]["sync_mode"] = "live_only"
        else:
            state["meta"]["sync_mode"] = "sync_failed"

        # Track sync health history for stale-data detection.
        sync_health = state.setdefault("sync_health", {})
        history = sync_health.get("history", [])
        if not isinstance(history, list):
            history = []

        history.append(
            {
                "timestamp": now_iso,
                "equity": state.get("paper_account", {}).get("equity"),
                "success": bool(paper_data),
            }
        )
        history = history[-24:]
        sync_health["history"] = history
        sync_health["last_attempt"] = now_iso
        sync_health["sync_source"] = "sync_alpaca_state.py"
        if paper_data:
            sync_health["last_successful_sync"] = now_iso
        sync_health["sync_count_today"] = len(
            [
                row
                for row in history
                if str(row.get("timestamp", "")).startswith(today_str) and row.get("success")
            ]
        )

    # Compute and persist milestone controller + North Star probability snapshot.
    try:
        from src.safety.milestone_controller import (
            apply_snapshot_to_state,
            compute_milestone_snapshot,
        )

        snapshot = compute_milestone_snapshot(
            state=state,
            state_path=SYSTEM_STATE_FILE,
            trades_path=PROJECT_ROOT / "data" / "trades.json",
        )
        apply_snapshot_to_state(state, snapshot)
    except Exception as e:
        logger.warning(f"Could not update milestone snapshot in system_state: {e}")

    # Compute weekly operating gate + contribution plan for North Star execution.
    try:
        from src.safety.north_star_operating_plan import apply_operating_plan_to_state

        apply_operating_plan_to_state(
            state,
            trades_path=PROJECT_ROOT / "data" / "trades.json",
            weekly_history_path=PROJECT_ROOT / "data" / "north_star_weekly_history.json",
        )
    except Exception as e:
        logger.warning(f"Could not update North Star operating plan in system_state: {e}")

    # Win-rate fields in system_state MUST be derived from the paired-trade ledger (trades.json),
    # not from raw Alpaca fills (which are not paired into outcomes).
    try:
        trades_payload = {}
        trades_path = PROJECT_ROOT / "data" / "trades.json"
        if trades_path.exists():
            with open(trades_path) as handle:
                trades_payload = json.load(handle) or {}

        stats = trades_payload.get("stats", {}) if isinstance(trades_payload, dict) else {}
        closed_trades = int(stats.get("closed_trades", 0) or 0)
        win_rate_pct = stats.get("win_rate_pct")
        win_rate_val = float(win_rate_pct) if win_rate_pct is not None else 0.0

        state.setdefault("paper_account", {})
        state["paper_account"]["win_rate"] = round(win_rate_val, 2)
        state["paper_account"]["win_rate_sample_size"] = closed_trades
    except Exception as e:
        logger.warning(f"Could not refresh win rate metrics from trades.json: {e}")

    # Write atomically
    SYSTEM_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_file = SYSTEM_STATE_FILE.with_suffix(".tmp")
    with open(temp_file, "w") as f:
        json.dump(state, f, indent=2)
    temp_file.rename(SYSTEM_STATE_FILE)

    # Log result
    paper_equity = state.get("paper_account", {}).get("equity", 0)
    live_equity = state.get("live_account", {}).get("equity", 0)
    positions_count = state.get("account", {}).get("positions_count", 0)
    logger.info(
        f"✅ Updated system_state.json (PAPER=${paper_equity:.2f}, LIVE=${live_equity:.2f}, positions={positions_count})"
    )


def main() -> int:
    """
    Main entry point.

    Returns:
        0 on success, 1 on failure
    """
    logger.info("=" * 60)
    logger.info("ALPACA STATE SYNC")
    logger.info("=" * 60)

    try:
        # Sync from Alpaca
        alpaca_data = sync_from_alpaca()

        # Update local state
        update_system_state(alpaca_data)

        logger.info("=" * 60)
        if alpaca_data is None:
            logger.info("⚠️ SYNC SKIPPED - No API keys")
            logger.info("   Existing data preserved, timestamp updated")
        else:
            paper_data = alpaca_data.get("paper") if isinstance(alpaca_data, dict) else None
            live_data = alpaca_data.get("live") if isinstance(alpaca_data, dict) else None
            logger.info("✅ SYNC COMPLETE")
            if paper_data:
                logger.info(f"   PAPER equity: ${paper_data.get('equity', 0):,.2f}")
                logger.info(f"   PAPER positions: {paper_data.get('positions_count', 0)}")
            if live_data:
                logger.info(f"   LIVE equity: ${live_data.get('equity', 0):,.2f}")
        logger.info("=" * 60)

        return 0

    except Exception as e:
        logger.error("=" * 60)
        logger.error(f"❌ SYNC FAILED: {e}")
        logger.error("   Trading should be BLOCKED until this is resolved.")
        logger.error("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
