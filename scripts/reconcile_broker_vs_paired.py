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
from collections import defaultdict
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


def _leg_key(row: dict[str, Any]) -> tuple:
    """Return a stable key identifying the option position this fill belongs to.

    For MLEG (multi-leg) parents we key on the sorted tuple of OCC leg symbols
    so that an opening IC and its offsetting closing IC land in the same bucket.
    For SIMPLE (single-leg) fills we key on the OCC symbol itself.
    """
    order_class = str(row.get("order_class") or "")
    if "MLEG" in order_class:
        legs = row.get("legs") or []
        # Legs may be OCC strings or dicts with a 'symbol' field; normalize.
        norm = []
        for leg in legs:
            if isinstance(leg, dict):
                norm.append(str(leg.get("symbol") or ""))
            else:
                norm.append(str(leg))
        return ("MLEG", tuple(sorted(norm)))
    return ("SIMPLE", str(row.get("symbol") or ""))


def _signed_qty(row: dict[str, Any]) -> float:
    """Return signed contract quantity (long positive, short negative).

    MLEG parents have no side; we infer direction from price sign:
      price > 0 (net credit received)  -> position opened short -> long-direction
                                          increase by +qty when the package is
                                          sold (we treat sell-to-open as the
                                          'reference' direction so the offsetting
                                          buy-to-close nets to zero).
      price < 0 (net debit paid)       -> the offsetting buy-to-close -> -qty.
    Convention is internal: we only care that opening + closing fills net to 0
    when the package is fully unwound.

    SIMPLE rows use the explicit side: SELL = +qty, BUY = -qty (same
    'short-as-reference' convention).
    """
    qty = _to_float(row.get("qty"), 0.0)
    order_class = str(row.get("order_class") or "")
    if "MLEG" in order_class:
        price = _to_float(row.get("price"), 0.0)
        if price > 0:
            return qty
        if price < 0:
            return -qty
        return 0.0
    side = str(row.get("side") or "")
    if "SELL" in side:
        return qty
    if "BUY" in side:
        return -qty
    return 0.0


def _row_timestamp(row: dict[str, Any]) -> str | None:
    """Return the best-available ISO timestamp for a fill row.

    Prefers filled_at, then submitted_at, then created_at. Returns the raw
    string (already ISO-ish in Alpaca data); comparison is lexicographic
    because all rows share the same '+00:00' suffix.
    """
    for key in ("filled_at", "submitted_at", "created_at"):
        val = row.get(key)
        if val:
            return str(val)
    return None


def compute_broker_realized(
    system_state: dict[str, Any],
) -> tuple[float, int, str | None, str | None]:
    """Return (broker_realized_dollars, closed_position_count, window_start, window_end).

    Sums signed_cash only for leg-key groups whose net quantity is zero (the
    position has been fully closed). Open positions contribute $0.

    The window is the [min, max] timestamp across the FILLED rows that
    contribute to closed leg-groups. Used by compute_paired_realized to
    apples-to-apples clip the paired ledger so the rolling 60d broker window
    is not diff'd against the full-history paired ledger.

    Bug history: the v1 of this function summed signed_cash across ALL fills,
    which conflated open-position entry cash with realized P/L and produced
    a $50K+ phantom delta against the paired ledger every day. See LL-354.
    """
    history = system_state.get("trade_history") or []
    fills = [row for row in history if "FILLED" in str(row.get("status") or "")]

    groups: dict[tuple, dict[str, Any]] = defaultdict(
        lambda: {"net_qty": 0.0, "cash": 0.0, "timestamps": []}
    )
    for row in fills:
        key = _leg_key(row)
        groups[key]["net_qty"] += _signed_qty(row)
        groups[key]["cash"] += _fill_signed_cash(row)
        ts = _row_timestamp(row)
        if ts:
            groups[key]["timestamps"].append(ts)

    closed_total = 0.0
    closed_count = 0
    closed_timestamps: list[str] = []
    for stats in groups.values():
        if abs(stats["net_qty"]) < 1e-6:
            closed_total += stats["cash"]
            closed_count += 1
            closed_timestamps.extend(stats["timestamps"])

    window_start = min(closed_timestamps) if closed_timestamps else None
    window_end = max(closed_timestamps) if closed_timestamps else None

    return round(closed_total, 2), closed_count, window_start, window_end


def compute_paired_realized(
    trades: dict[str, Any],
    window_start: str | None = None,
    window_end: str | None = None,
) -> dict[str, Any]:
    """Return paired realized P/L, optionally clipped to a broker window.

    When window_start/window_end are provided, the per-trade ``trades[]`` list
    is filtered by ``exit_time`` (realized P/L is booked at exit). The bucket
    inside the window drives the reconciliation delta; the outside bucket is
    surfaced informationally so a long-history vs short-window mismatch
    cannot silently train the operator to ignore alerts.

    When no window is supplied, falls back to the legacy stats-only path
    (stats.total_pnl + stats.unpaired_realized_pnl) so older callers and
    tests keep working.

    Schema (post PR #4076):
      stats.total_pnl            -> paired closed-trade P/L
      stats.unpaired_realized_pnl -> singleton fills not yet paired (optional)

    Returns a dict so the report payload can include both in/out bucket
    counts without further tuple-arity churn.
    """
    stats = trades.get("stats") or {}
    unpaired = _to_float(stats.get("unpaired_realized_pnl"), 0.0)
    unpaired_order_count = int(stats.get("unpaired_order_count") or 0)

    if window_start is None or window_end is None:
        # Legacy path: stats-only, no clipping.
        total_pnl = _to_float(stats.get("total_pnl"), 0.0)
        paired_trade_count = int(stats.get("closed_trades") or 0)
        return {
            "paired_realized_in_window": round(total_pnl + unpaired, 2),
            "paired_realized_outside_window": 0.0,
            "paired_trade_count_in_window": paired_trade_count,
            "paired_trade_count_outside_window": 0,
            "unpaired_order_count": unpaired_order_count,
            "window_clipped": False,
        }

    in_pnl = 0.0
    out_pnl = 0.0
    in_count = 0
    out_count = 0
    for trade in trades.get("trades") or []:
        if str(trade.get("status") or "").lower() != "closed":
            continue
        exit_time = str(trade.get("exit_time") or "")
        pnl = _to_float(trade.get("realized_pnl"), 0.0)
        if exit_time and window_start <= exit_time <= window_end:
            in_pnl += pnl
            in_count += 1
        else:
            out_pnl += pnl
            out_count += 1

    # Unpaired singletons fold into the in-window bucket (the broker fills
    # that generated them are themselves window-resident by construction).
    in_pnl += unpaired

    return {
        "paired_realized_in_window": round(in_pnl, 2),
        "paired_realized_outside_window": round(out_pnl, 2),
        "paired_trade_count_in_window": in_count,
        "paired_trade_count_outside_window": out_count,
        "unpaired_order_count": unpaired_order_count,
        "window_clipped": True,
    }


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
    paired: dict[str, Any],
    broker_fill_count: int,
    window_start: str | None,
    window_end: str | None,
    notes: str,
) -> dict[str, Any]:
    paired_in = paired["paired_realized_in_window"]
    delta = compute_delta(broker_realized, paired_in)
    alert_fired = abs(delta) > THRESHOLD_DOLLARS
    return {
        "date": date_str,
        "broker_realized_pnl": broker_realized,
        # Back-compat: keep paired_realized_pnl == in-window so any
        # downstream consumer that read the v1 field doesn't break.
        "paired_realized_pnl": paired_in,
        "paired_realized_in_window": paired_in,
        "paired_realized_outside_window": paired["paired_realized_outside_window"],
        "paired_trade_count_in_window": paired["paired_trade_count_in_window"],
        "paired_trade_count_outside_window": paired["paired_trade_count_outside_window"],
        "window_clipped": paired["window_clipped"],
        "window_start": window_start,
        "window_end": window_end,
        "delta_dollars": delta,
        "threshold_dollars": THRESHOLD_DOLLARS,
        "alert_fired": alert_fired,
        "broker_fill_count": broker_fill_count,
        # Back-compat name for the old test (== in-window count).
        "paired_trade_count": paired["paired_trade_count_in_window"],
        "paired_unpaired_order_count": paired["unpaired_order_count"],
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

    (
        broker_realized,
        broker_closed_count,
        window_start,
        window_end,
    ) = compute_broker_realized(system_state)
    paired = compute_paired_realized(trades, window_start, window_end)

    date_str = args.date or _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d")
    notes = (
        "broker_realized = sum(signed_cash) over FILLED rows grouped by "
        "leg-key (SIMPLE: OCC symbol; MLEG: sorted tuple of leg symbols) "
        "where net signed_qty == 0 (position fully closed). Open positions "
        "contribute $0 so entry cash is not mistaken for realized P/L. "
        "paired_realized_in_window = sum(trades[].realized_pnl) where "
        "exit_time in [window_start, window_end] + "
        "trades.stats.unpaired_realized_pnl. The window is the min/max "
        "filled_at across closed broker leg-groups, so the rolling ~60d "
        "broker history is not diff'd against the full paired ledger. "
        "Threshold $150 sits above the ~$103 fee/spread noise floor "
        "(LL-354 prevention layer)."
    )

    payload = build_payload(
        date_str=date_str,
        broker_realized=broker_realized,
        paired=paired,
        broker_fill_count=broker_closed_count,
        window_start=window_start,
        window_end=window_end,
        notes=notes,
    )

    report_path = write_report(args.report_dir, payload)
    logger.info("Reconciliation report written: %s", report_path)
    logger.info(
        "broker=$%.2f  paired_in=$%.2f  paired_out=$%.2f  delta=$%.2f  threshold=$%.2f  window=[%s, %s]",
        payload["broker_realized_pnl"],
        payload["paired_realized_in_window"],
        payload["paired_realized_outside_window"],
        payload["delta_dollars"],
        payload["threshold_dollars"],
        payload["window_start"],
        payload["window_end"],
    )

    fired = maybe_alert(payload)
    return 2 if fired else 0


if __name__ == "__main__":
    sys.exit(main())
