"""
Zombie Order Cleanup Module

Monitors and cancels stale/unfilled orders that have been pending too long.
Prevents phantom fills and reduces exposure from forgotten limit orders.

This addresses a real risk: limit orders that sit unfilled can get executed
later when market conditions change, potentially causing unwanted fills.

Usage:
    # Run cleanup
    from src.safety.zombie_order_cleanup import cleanup_zombie_orders
    result = cleanup_zombie_orders(max_age_seconds=60)

    # As cron job (every 5 minutes during market hours)
    python3 -c "from src.safety.zombie_order_cleanup import cleanup_zombie_orders; cleanup_zombie_orders()"

Configuration:
    ZOMBIE_ORDER_MAX_AGE_SECONDS: Max age for pending orders (default: 60)
    ZOMBIE_ORDER_ENABLED: Enable/disable cleanup (default: true)

Author: Trading System
Created: 2025-12-11
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Configuration
DEFAULT_MAX_AGE_SECONDS = int(os.getenv("ZOMBIE_ORDER_MAX_AGE_SECONDS", "60"))
CLEANUP_ENABLED = os.getenv("ZOMBIE_ORDER_ENABLED", "true").lower() in ("true", "1", "yes")
STATE_FILE = Path("data/zombie_order_cleanup_state.json")

# Order statuses that indicate a "zombie" (stale pending order)
PENDING_STATUSES = {
    "new",
    "accepted",
    "pending_new",
    "accepted_for_bidding",
    "partially_filled",
}


def get_alpaca_client():
    """Get Alpaca trading client."""
    try:
        from alpaca.trading.client import TradingClient

        api_key = os.getenv("ALPACA_API_KEY")
        secret_key = os.getenv("ALPACA_SECRET_KEY")

        if not api_key or not secret_key:
            logger.error("Missing Alpaca API credentials")
            return None

        return TradingClient(api_key=api_key, secret_key=secret_key, paper=True)
    except Exception as e:
        logger.error(f"Failed to create Alpaca client: {e}")
        return None


def get_pending_orders(client) -> list[dict[str, Any]]:
    """Get all pending/open orders from Alpaca."""
    try:
        from alpaca.trading.requests import GetOrdersRequest
        from alpaca.trading.enums import QueryOrderStatus

        request = GetOrdersRequest(status=QueryOrderStatus.OPEN)
        orders = client.get_orders(request)

        pending = []
        for order in orders:
            status = str(order.status).lower()
            if status in PENDING_STATUSES:
                pending.append({
                    "id": str(order.id),
                    "symbol": order.symbol,
                    "side": str(order.side),
                    "qty": str(order.qty),
                    "order_type": str(order.type),
                    "status": status,
                    "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None,
                    "created_at": order.created_at.isoformat() if order.created_at else None,
                    "time_in_force": str(order.time_in_force),
                })
        return pending

    except Exception as e:
        logger.error(f"Failed to fetch pending orders: {e}")
        return []


def cancel_order(client, order_id: str) -> bool:
    """Cancel a specific order."""
    try:
        client.cancel_order_by_id(order_id)
        return True
    except Exception as e:
        logger.warning(f"Failed to cancel order {order_id}: {e}")
        return False


def calculate_order_age(order: dict[str, Any]) -> timedelta:
    """Calculate how long an order has been pending."""
    submitted_at = order.get("submitted_at") or order.get("created_at")
    if not submitted_at:
        return timedelta(seconds=0)

    try:
        if isinstance(submitted_at, str):
            # Parse ISO format timestamp
            submitted_time = datetime.fromisoformat(submitted_at.replace("Z", "+00:00"))
        else:
            submitted_time = submitted_at

        now = datetime.now(timezone.utc)
        return now - submitted_time
    except Exception as e:
        logger.debug(f"Could not parse timestamp: {e}")
        return timedelta(seconds=0)


def load_state() -> dict[str, Any]:
    """Load cleanup state from disk."""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "total_cancelled": 0,
        "last_cleanup": None,
        "cancelled_orders": [],
    }


def save_state(state: dict[str, Any]) -> None:
    """Save cleanup state to disk."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        # Keep only last 100 cancelled orders
        state["cancelled_orders"] = state.get("cancelled_orders", [])[-100:]
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save state: {e}")


def cleanup_zombie_orders(
    max_age_seconds: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Cancel orders that have been pending too long.

    Args:
        max_age_seconds: Maximum age in seconds before an order is considered zombie
        dry_run: If True, only report what would be cancelled without actually cancelling

    Returns:
        Dict with cleanup results including:
        - pending_count: Number of pending orders found
        - zombie_count: Number of zombie orders identified
        - cancelled_count: Number of orders cancelled
        - cancelled_orders: List of cancelled order details
    """
    if not CLEANUP_ENABLED and not dry_run:
        return {
            "status": "disabled",
            "message": "Zombie order cleanup is disabled via ZOMBIE_ORDER_ENABLED=false",
        }

    max_age = max_age_seconds or DEFAULT_MAX_AGE_SECONDS
    max_age_delta = timedelta(seconds=max_age)

    result = {
        "timestamp": datetime.now().isoformat(),
        "max_age_seconds": max_age,
        "dry_run": dry_run,
        "pending_count": 0,
        "zombie_count": 0,
        "cancelled_count": 0,
        "cancelled_orders": [],
        "errors": [],
    }

    logger.info(f"Starting zombie order cleanup (max_age={max_age}s, dry_run={dry_run})")

    # Get Alpaca client
    client = get_alpaca_client()
    if not client:
        result["status"] = "error"
        result["errors"].append("Failed to create Alpaca client")
        return result

    # Get pending orders
    pending_orders = get_pending_orders(client)
    result["pending_count"] = len(pending_orders)

    if not pending_orders:
        result["status"] = "ok"
        result["message"] = "No pending orders found"
        logger.info("No pending orders to check")
        return result

    logger.info(f"Found {len(pending_orders)} pending orders")

    # Identify and cancel zombie orders
    state = load_state()
    zombies_found = []

    for order in pending_orders:
        age = calculate_order_age(order)

        if age > max_age_delta:
            zombies_found.append({
                **order,
                "age_seconds": age.total_seconds(),
            })

            logger.warning(
                f"Zombie order detected: {order['symbol']} {order['side']} "
                f"{order['qty']} ({order['order_type']}) - age: {age.total_seconds():.0f}s"
            )

            if not dry_run:
                if cancel_order(client, order["id"]):
                    result["cancelled_count"] += 1
                    result["cancelled_orders"].append({
                        "id": order["id"],
                        "symbol": order["symbol"],
                        "side": order["side"],
                        "qty": order["qty"],
                        "age_seconds": age.total_seconds(),
                        "cancelled_at": datetime.now().isoformat(),
                    })
                    state["total_cancelled"] = state.get("total_cancelled", 0) + 1
                    state["cancelled_orders"].append({
                        "id": order["id"],
                        "symbol": order["symbol"],
                        "cancelled_at": datetime.now().isoformat(),
                    })
                else:
                    result["errors"].append(f"Failed to cancel order {order['id']}")

    result["zombie_count"] = len(zombies_found)

    if dry_run:
        result["status"] = "dry_run"
        result["message"] = f"Would cancel {len(zombies_found)} zombie orders"
    else:
        result["status"] = "ok"
        result["message"] = f"Cancelled {result['cancelled_count']} of {len(zombies_found)} zombie orders"
        state["last_cleanup"] = datetime.now().isoformat()
        save_state(state)

    logger.info(f"Cleanup complete: {result['message']}")
    return result


def get_cleanup_status() -> dict[str, Any]:
    """Get current zombie order cleanup status and history."""
    state = load_state()
    return {
        "enabled": CLEANUP_ENABLED,
        "max_age_seconds": DEFAULT_MAX_AGE_SECONDS,
        "total_cancelled_lifetime": state.get("total_cancelled", 0),
        "last_cleanup": state.get("last_cleanup"),
        "recent_cancellations": state.get("cancelled_orders", [])[-10:],
    }


# CLI interface
if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    parser = argparse.ArgumentParser(description="Zombie Order Cleanup")
    parser.add_argument(
        "--max-age",
        type=int,
        default=DEFAULT_MAX_AGE_SECONDS,
        help=f"Max age in seconds for pending orders (default: {DEFAULT_MAX_AGE_SECONDS})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report zombie orders without cancelling",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show cleanup status and history",
    )

    args = parser.parse_args()

    if args.status:
        status = get_cleanup_status()
        print(json.dumps(status, indent=2))
    else:
        result = cleanup_zombie_orders(
            max_age_seconds=args.max_age,
            dry_run=args.dry_run,
        )
        print(json.dumps(result, indent=2))
