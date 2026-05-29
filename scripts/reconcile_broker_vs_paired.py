#!/usr/bin/env python3
"""Daily broker-vs-paired P/L reconciliation alert.

Prevention layer for LL-354 (the $2.6K paired-vs-broker gap that stayed hidden
for ~4 months because nothing diffed the two numbers).

Compares:
  - broker_realized: sum of signed_cash for every fill in
    data/system_state.json -> trade_history
  - paired_realized: data/trades.json -> stats.total_pnl
    + stats.unpaired_realized_pnl

If |delta| > THRESHOLD_DOLLARS ($150, set above the ~$103 fee/spread noise
floor), capture a Sentry message and exit 2 so the workflow surfaces it.
The daily JSON report is always written.

Karpathy-style: single script, plain functions, no classes.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

THRESHOLD_DOLLARS = 150.0
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SYSTEM_STATE = REPO_ROOT / "data" / "system_state.json"
DEFAULT_TRADES = REPO_ROOT / "data" / "trades.json"
DEFAULT_REPORT_DIR = REPO_ROOT / "data" / "reports"

logger = logging.getLogger("reconcile_broker_vs_paired")


def _to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _fill_signed_cash(row: dict[str, Any]) -> float:
    """Return signed cash flow (in dollars) for one fill row.

    Convention (options, contract multiplier = 100):
      - For MLEG parent rows side is None/"None"; the parent ``price`` is
        already signed (negative = net debit paid, positive = net credit
        received), so cash = qty * price * 100.
      - For SIMPLE single-leg rows side is OrderSide.BUY/OrderSide.SELL;
        SELL = +qty*price*100, BUY = -qty*price*100.
    """
    status = str(row.get("status") or "")
    if "FILLED" not in status:
        return 0.0

    qty = _to_float(row.get("qty"), 0.0)
    price = _to_float(row.get("price"), 0.0)
    side = str(row.get("side") or "")
    order_class = str(row.get("order_class") or "")

    if "MLEG" in order_class:
        # Parent price is already signed (debit negative, credit positive).
        return qty * price * 100.0

    if "SELL" in side:
        return qty * price * 100.0
    if "BUY" in side:
        return -qty * price * 100.0

    return 0.0


def compute_broker_realized(system_state: dict[str, Any]) -> tuple[float, int]:
    """Return (broker_realized_dollars, fill_count) from system_state.json."""
    history = system_state.get("trade_history") or []
    fills = [row for row in history if "FILLED" in str(row.get("status") or "")]
    total = sum(_fill_signed_cash(row) for row in fills)
    return round(total, 2), len(fills)


def compute_paired_realized(trades: dict[str, Any]) -> tuple[float, int, int]:
    """Return (paired_realized_dollars, paired_trade_count, unpaired_order_count).

    Schema (post PR #4076):
      stats.total_pnl            -> paired closed-trade P/L
      stats.unpaired_realized_pnl -> singleton fills not yet paired (optional)
    """
    stats = trades.get("stats") or {}
    total_pnl = _to_float(stats.get("total_pnl"), 0.0)
    unpaired = _to_float(stats.get("unpaired_realized_pnl"), 0.0)
    paired_trade_count = int(stats.get("closed_trades") or 0)
    unpaired_order_count = int(stats.get("unpaired_order_count") or 0)
    return round(total_pnl + unpaired, 2), paired_trade_count, unpaired_order_count


def compute_delta(broker_realized: float, paired_realized: float) -> float:
    return round(broker_realized - paired_realized, 2)


def write_report(report_dir: Path, payload: dict[str, Any]) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    date_str = payload["date"]
    path = report_dir / f"reconciliation_{date_str}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path


def maybe_alert(payload: dict[str, Any]) -> bool:
    """Fire Sentry alert if |delta| > threshold.

    Returns True if alert was fired (regardless of whether Sentry transport
    succeeded). If SENTRY_DSN is unset or sentry_sdk is unavailable, log a
    CRITICAL line and continue — per spec, do not crash.
    """
    delta = abs(payload["delta_dollars"])
    threshold = payload["threshold_dollars"]
    if delta <= threshold:
        return False

    msg = (
        f"Broker-vs-paired P/L reconciliation breach: "
        f"|delta|=${delta:.2f} > ${threshold:.2f} "
        f"(broker={payload['broker_realized_pnl']:.2f}, "
        f"paired={payload['paired_realized_pnl']:.2f}, "
        f"date={payload['date']})"
    )

    dsn = os.environ.get("SENTRY_DSN", "").strip()
    if not dsn:
        logger.critical("[NO SENTRY_DSN] %s", msg)
        return True

    try:
        import sentry_sdk  # type: ignore
    except ImportError:
        logger.critical("[NO sentry_sdk] %s", msg)
        return True

    try:
        sentry_sdk.init(dsn=dsn)
        sentry_sdk.capture_message(msg, level="error")
    except Exception as exc:  # noqa: BLE001 - never crash the reconciler
        logger.critical("[SENTRY_FAILED:%s] %s", exc, msg)
    return True


def build_payload(
    *,
    date_str: str,
    broker_realized: float,
    paired_realized: float,
    broker_fill_count: int,
    paired_trade_count: int,
    paired_unpaired_order_count: int,
    notes: str,
) -> dict[str, Any]:
    delta = compute_delta(broker_realized, paired_realized)
    alert_fired = abs(delta) > THRESHOLD_DOLLARS
    return {
        "date": date_str,
        "broker_realized_pnl": broker_realized,
        "paired_realized_pnl": paired_realized,
        "delta_dollars": delta,
        "threshold_dollars": THRESHOLD_DOLLARS,
        "alert_fired": alert_fired,
        "broker_fill_count": broker_fill_count,
        "paired_trade_count": paired_trade_count,
        "paired_unpaired_order_count": paired_unpaired_order_count,
        "notes": notes,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--system-state", type=Path, default=DEFAULT_SYSTEM_STATE)
    parser.add_argument("--trades", type=Path, default=DEFAULT_TRADES)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--date", type=str, default=None,
                        help="Override report date (YYYY-MM-DD). Default = today UTC.")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if not args.system_state.exists():
        logger.critical("system_state.json missing at %s", args.system_state)
        return 3
    if not args.trades.exists():
        logger.critical("trades.json missing at %s", args.trades)
        return 3

    system_state = json.loads(args.system_state.read_text())
    trades = json.loads(args.trades.read_text())

    broker_realized, broker_fill_count = compute_broker_realized(system_state)
    paired_realized, paired_trade_count, unpaired_order_count = compute_paired_realized(trades)

    date_str = args.date or _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d")
    notes = (
        "broker_realized = sum(signed_cash) over all FILLED rows in "
        "system_state.trade_history. paired_realized = "
        "trades.stats.total_pnl + trades.stats.unpaired_realized_pnl. "
        "Threshold $150 sits above the ~$103 fee/spread noise floor "
        "(LL-354 prevention layer)."
    )

    payload = build_payload(
        date_str=date_str,
        broker_realized=broker_realized,
        paired_realized=paired_realized,
        broker_fill_count=broker_fill_count,
        paired_trade_count=paired_trade_count,
        paired_unpaired_order_count=unpaired_order_count,
        notes=notes,
    )

    report_path = write_report(args.report_dir, payload)
    logger.info("Reconciliation report written: %s", report_path)
    logger.info(
        "broker=$%.2f  paired=$%.2f  delta=$%.2f  threshold=$%.2f",
        payload["broker_realized_pnl"],
        payload["paired_realized_pnl"],
        payload["delta_dollars"],
        payload["threshold_dollars"],
    )

    fired = maybe_alert(payload)
    return 2 if fired else 0


if __name__ == "__main__":
    sys.exit(main())
