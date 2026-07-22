#!/usr/bin/env python3
"""Surgically reduce broker-confirmed excess option inventory.

Execution reconstructs active iron condors from filled MLEG opening orders.
This matters when two valid structures share an expiry or vertical: the legacy
``data/ic_entries.json`` key can represent only one structure per expiry and
must never be the authority for a destructive close.  Any unexplained live leg
or pending option order blocks execution.

Journal/state comparison remains available as a non-authoritative dry-run.

Usage:
  .venv/bin/python scripts/reconcile_open_inventory.py --dry-run
  .venv/bin/python scripts/reconcile_open_inventory.py --execute-paper
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("reconcile_open_inventory")

OCC = re.compile(r"^([A-Z]+)(\d{6})([CP])(\d{8})$")
ENTRIES = ROOT / "data" / "ic_entries.json"
STATE = ROOT / "data" / "system_state.json"
PCS_ENTRIES = ROOT / "data" / "put_credit_entries.json"


def _parse(sym: str, qty: float) -> dict | None:
    m = OCC.match(sym.strip().upper())
    if not m:
        return None
    root, ymd, right, strike_raw = m.groups()
    return {
        "symbol": sym.strip().upper(),
        "root": root,
        "expiry_ymd": ymd,
        "right": right,
        "strike": int(strike_raw) / 1000.0,
        "qty": float(qty),
    }


def _expected_from_ic_entries(entries: dict) -> dict[str, float]:
    """Map OCC symbol -> signed qty expected for open journaled ICs."""
    expected: dict[str, float] = {}
    for key, entry in entries.items():
        if not isinstance(entry, dict):
            continue
        if not key.startswith("IC_"):
            continue
        strikes = entry.get("strikes") or {}
        try:
            qty = abs(float(entry.get("quantity") or 1))
            sp = float(strikes["short_put"])
            lp = float(strikes["long_put"])
            sc = float(strikes["short_call"])
            lc = float(strikes["long_call"])
        except (KeyError, TypeError, ValueError):
            continue
        # expiry from key IC_260821
        ymd = key.replace("IC_", "")
        if len(ymd) != 6:
            continue

        def occ(right: str, strike: float) -> str:
            return f"SPY{ymd}{right}{int(strike * 1000):08d}"

        expected[occ("P", sp)] = expected.get(occ("P", sp), 0.0) - qty
        expected[occ("P", lp)] = expected.get(occ("P", lp), 0.0) + qty
        expected[occ("C", sc)] = expected.get(occ("C", sc), 0.0) - qty
        expected[occ("C", lc)] = expected.get(occ("C", lc), 0.0) + qty
    return expected


def _expected_from_put_credit(entries: dict) -> dict[str, float]:
    from scripts.residual_ic_manager import active_pcs_expected

    return active_pcs_expected(entries)


def plan_reductions(actual_legs: list[dict], expected: dict[str, float]) -> list[dict]:
    """Return close actions to make actual match expected (excess only)."""
    actual: dict[str, float] = defaultdict(float)
    for leg in actual_legs:
        actual[leg["symbol"]] += leg["qty"]

    actions = []
    # Symbols only in actual, or qty differs
    for sym, aqty in sorted(actual.items()):
        eqty = float(expected.get(sym, 0.0))
        # excess = actual - expected (in same sign domain)
        # e.g. actual -2, expected -1 → excess short 1 → buy 1 to close
        # actual +2, expected +1 → excess long 1 → sell 1 to close
        # actual -1, expected 0 → excess short 1 → buy 1
        delta = aqty - eqty
        if abs(delta) < 1e-9:
            continue
        if delta < 0:
            # too short / not long enough → buy |delta| to close excess short
            actions.append(
                {
                    "symbol": sym,
                    "side": "buy",
                    "qty": abs(delta),
                    "reason": f"reduce excess short (actual={aqty}, expected={eqty})",
                    "actual": aqty,
                    "expected": eqty,
                }
            )
        else:
            actions.append(
                {
                    "symbol": sym,
                    "side": "sell",
                    "qty": abs(delta),
                    "reason": f"reduce excess long (actual={aqty}, expected={eqty})",
                    "actual": aqty,
                    "expected": eqty,
                }
            )
    return actions


def load_legs_from_state() -> list[dict]:
    if not STATE.exists():
        return []
    state = json.loads(STATE.read_text(encoding="utf-8"))
    legs = []
    for row in state.get("positions") or []:
        if not isinstance(row, dict):
            continue
        sym = row.get("symbol")
        try:
            qty = float(row.get("qty", row.get("quantity", 0)) or 0)
        except (TypeError, ValueError):
            qty = 0.0
        parsed = _parse(str(sym), qty) if sym else None
        if parsed and abs(parsed["qty"]) > 1e-9:
            legs.append(parsed)
    return legs


def load_legs_from_broker() -> tuple[Any, list[dict], list[Any]]:
    from alpaca.trading.client import TradingClient
    from src.utils.alpaca_client import get_alpaca_credentials

    key, secret = get_alpaca_credentials()
    if not key or not secret:
        raise RuntimeError("Alpaca credentials missing")
    client = TradingClient(key, secret, paper=True)
    positions = list(client.get_all_positions())
    legs = []
    for p in positions:
        parsed = _parse(str(p.symbol), float(p.qty))
        if parsed:
            legs.append(parsed)
    return client, legs, positions


def _expected_from_recovered_structures(structures: list[dict[str, Any]]) -> dict[str, float]:
    """Aggregate signed quantities from broker-confirmed opening structures."""

    expected: dict[str, float] = defaultdict(float)
    for structure in structures:
        for leg in structure.get("legs") or []:
            symbol = str(leg.get("symbol") or "")
            if symbol:
                expected[symbol] += float(leg.get("qty") or 0)
    return dict(expected)


def _is_option_order(order: Any) -> bool:
    symbols = [str(getattr(leg, "symbol", "") or "") for leg in getattr(order, "legs", None) or []]
    parent_symbol = str(getattr(order, "symbol", "") or "")
    if parent_symbol:
        symbols.append(parent_symbol)
    return any(_parse(symbol, 0) is not None for symbol in symbols)


def broker_confirmed_expected(
    positions: list[Any],
    all_orders: list[Any],
    open_orders: list[Any],
    pcs_expected: dict[str, float],
) -> tuple[dict[str, float], dict[str, Any]]:
    """Resolve execution authority or raise instead of guessing.

    Filled IC opening orders explain the legacy inventory.  Remaining position
    quantities must exactly match the independent put-credit journal.  A
    pending option order makes the position snapshot unstable, so execution is
    blocked until the broker settles or cancels it.
    """

    from scripts.residual_ic_manager import recover_active_structures

    pending = [
        str(getattr(order, "id", "") or getattr(order, "client_order_id", "") or "unknown")
        for order in open_orders
        if _is_option_order(order)
    ]
    if pending:
        raise RuntimeError(f"pending option orders make inventory unstable: {pending}")

    structures, unresolved = recover_active_structures(positions, all_orders)
    symbols = set(unresolved) | set(pcs_expected)
    mismatches = {
        symbol: {
            "unresolved_broker_qty": float(unresolved.get(symbol, 0.0)),
            "journaled_pcs_qty": float(pcs_expected.get(symbol, 0.0)),
        }
        for symbol in sorted(symbols)
        if abs(float(unresolved.get(symbol, 0.0)) - float(pcs_expected.get(symbol, 0.0)))
        > 1e-9
    }
    if mismatches:
        raise RuntimeError(f"unexplained broker inventory: {mismatches}")

    expected = _expected_from_recovered_structures(structures)
    for symbol, qty in pcs_expected.items():
        expected[symbol] = expected.get(symbol, 0.0) + qty
    evidence = {
        "source": "broker_filled_orders_plus_pcs_journal",
        "recovered_ic_structures": len(structures),
        "unresolved_matched_to_pcs": unresolved,
        "pending_option_orders": [],
    }
    return expected, evidence


def _quote_limit(client, symbol: str, side: str) -> float | None:
    """Best-effort limit from latest trade/quote; fallback None → skip."""
    try:
        from alpaca.data.historical.option import OptionHistoricalDataClient
        from alpaca.data.requests import OptionLatestQuoteRequest
        from src.utils.alpaca_client import get_alpaca_credentials

        key, secret = get_alpaca_credentials()
        data = OptionHistoricalDataClient(key, secret)
        q = data.get_option_latest_quote(OptionLatestQuoteRequest(symbol_or_symbols=symbol))
        quote = q.get(symbol) if isinstance(q, dict) else None
        if quote is None and hasattr(q, "values"):
            vals = list(q.values())
            quote = vals[0] if vals else None
        if quote is None:
            return None
        bid = float(getattr(quote, "bid_price", 0) or 0)
        ask = float(getattr(quote, "ask_price", 0) or 0)
        if side == "buy":
            # pay up to ask (or mid+slip)
            if ask > 0:
                return round(ask, 2)
            if bid > 0:
                return round(bid + 0.05, 2)
        else:
            if bid > 0:
                return round(bid, 2)
            if ask > 0:
                return round(max(0.01, ask - 0.05), 2)
    except Exception as exc:  # noqa: BLE001
        logger.debug("quote failed %s: %s", symbol, exc)
    return None


def _pair_vertical_actions(actions: list[dict]) -> list[list[dict]]:
    """Group buy+sell on same expiry/right into 2-leg vertical closes when possible."""
    remaining = list(actions)
    groups: list[list[dict]] = []
    used: set[int] = set()
    for i, a in enumerate(remaining):
        if i in used:
            continue
        ma = OCC.match(a["symbol"])
        if not ma:
            groups.append([a])
            used.add(i)
            continue
        _, ymd, right, _ = ma.groups()
        partner = None
        for j, b in enumerate(remaining):
            if j in used or j == i:
                continue
            mb = OCC.match(b["symbol"])
            if not mb:
                continue
            _, ymd2, right2, _ = mb.groups()
            if ymd2 != ymd or right2 != right:
                continue
            # one buy one sell, same qty
            if a["side"] != b["side"] and abs(a["qty"] - b["qty"]) < 1e-9:
                partner = j
                break
        if partner is not None:
            groups.append([a, remaining[partner]])
            used.add(i)
            used.add(partner)
        else:
            groups.append([a])
            used.add(i)
    return groups


def execute_actions(client, actions: list[dict], dry_run: bool) -> int:
    """Close excess via MLEG verticals when possible (avoids naked/uncovered rejects)."""
    from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
    from alpaca.trading.requests import LimitOrderRequest, OptionLegRequest
    from src.safety.mandatory_trade_gate import safe_submit_order

    if dry_run:
        for act in actions:
            logger.info("DRY %s %sx %s — %s", act["side"], act["qty"], act["symbol"], act["reason"])
        return len(actions)

    n = 0
    for group in _pair_vertical_actions(actions):
        if len(group) == 2:
            a, b = group
            qty = int(round(a["qty"]))
            legs = []
            for act in (a, b):
                side = OrderSide.BUY if act["side"] == "buy" else OrderSide.SELL
                legs.append(
                    OptionLegRequest(symbol=act["symbol"], side=side, ratio_qty=1)
                )
            # Net limit: buy-side pays ask, sell-side receives bid → debit positive
            buy = next(x for x in (a, b) if x["side"] == "buy")
            sell = next(x for x in (a, b) if x["side"] == "sell")
            buy_px = _quote_limit(client, buy["symbol"], "buy") or 0.0
            sell_px = _quote_limit(client, sell["symbol"], "sell") or 0.0
            # Alpaca multi-leg: positive limit = debit, negative = credit
            net = round(buy_px - sell_px, 2)
            if net == 0:
                net = 0.05
            logger.info(
                "MLEG close %s + %s qty=%s net_limit=%s",
                a["symbol"],
                b["symbol"],
                qty,
                net,
            )
            try:
                order = safe_submit_order(
                    client,
                    LimitOrderRequest(
                        qty=qty,
                        order_class=OrderClass.MLEG,
                        legs=legs,
                        time_in_force=TimeInForce.DAY,
                        limit_price=net,
                    ),
                    strategy="inventory_reconcile",
                )
                logger.info("  submitted %s status=%s", order.id, order.status)
                n += 1
            except Exception as exc:  # noqa: BLE001
                logger.error("  MLEG failed: %s", exc)
            continue

        # Single-leg fallback
        act = group[0]
        side = OrderSide.BUY if act["side"] == "buy" else OrderSide.SELL
        qty = int(round(act["qty"]))
        logger.info("%s %sx %s — %s", side.name, qty, act["symbol"], act["reason"])
        limit = _quote_limit(client, act["symbol"], act["side"])
        try:
            kwargs = {
                "symbol": act["symbol"],
                "qty": qty,
                "side": side,
                "time_in_force": TimeInForce.DAY,
            }
            try:
                from alpaca.trading.enums import PositionIntent

                kwargs["position_intent"] = (
                    PositionIntent.BUY_TO_CLOSE
                    if act["side"] == "buy"
                    else PositionIntent.SELL_TO_CLOSE
                )
            except Exception:
                pass
            if limit and limit > 0:
                req = LimitOrderRequest(limit_price=limit, **kwargs)
            else:
                from alpaca.trading.requests import MarketOrderRequest

                req = MarketOrderRequest(**kwargs)
            order = safe_submit_order(client, req, strategy="inventory_reconcile")
            logger.info("  submitted %s status=%s", order.id, order.status)
            n += 1
        except Exception as exc:  # noqa: BLE001
            logger.error("  failed %s: %s", act["symbol"], exc)
    return n


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute-paper", action="store_true")
    parser.add_argument(
        "--from-state",
        action="store_true",
        help="Plan from system_state.json only (no broker)",
    )
    args = parser.parse_args()
    dry = not args.execute_paper

    if args.execute_paper and args.from_state:
        logger.error("Execution requires live broker positions and filled-order reconstruction")
        return 2

    entries: dict = {}
    if ENTRIES.exists():
        entries = json.loads(ENTRIES.read_text(encoding="utf-8"))
    journal_expected = _expected_from_ic_entries(entries if isinstance(entries, dict) else {})
    pcs_expected: dict[str, float] = {}
    if PCS_ENTRIES.exists():
        pcs = json.loads(PCS_ENTRIES.read_text(encoding="utf-8"))
        if isinstance(pcs, dict):
            pcs_expected = _expected_from_put_credit(pcs)
            for k, v in pcs_expected.items():
                journal_expected[k] = journal_expected.get(k, 0.0) + v

    client = None
    evidence: dict[str, Any] = {"source": "journal_state_dry_run"}
    if args.from_state:
        legs = load_legs_from_state()
        expected = journal_expected
    else:
        try:
            client, legs, positions = load_legs_from_broker()
        except Exception as exc:
            if args.execute_paper:
                logger.error("Live broker inventory unavailable; execution blocked: %s", exc)
                return 2
            logger.warning(
                "Broker load failed (%s); using untrusted state for dry-run only", exc
            )
            legs = load_legs_from_state()
            expected = journal_expected
            evidence = {"source": "journal_state_fallback", "broker_error": str(exc)}
        else:
            from scripts.residual_ic_manager import _get_orders

            try:
                expected, evidence = broker_confirmed_expected(
                    positions,
                    _get_orders(client),
                    _get_orders(client, open_only=True),
                    pcs_expected,
                )
            except RuntimeError as exc:
                logger.error("Broker-confirmed reconciliation blocked: %s", exc)
                return 2

    if not legs:
        logger.info("No open option legs")
        return 0

    logger.info("Open legs: %s", len(legs))
    for leg in legs:
        logger.info(
            "  %s qty=%s expected=%s",
            leg["symbol"],
            leg["qty"],
            expected.get(leg["symbol"], 0.0),
        )

    actions = plan_reductions(legs, expected)
    if not actions:
        logger.info("Inventory matches %s — no reductions needed", evidence["source"])
        return 0

    logger.info("Planned reductions: %s", len(actions))
    for a in actions:
        logger.info("  %s", a)

    out = ROOT / "data" / "audit" / "inventory_reconcile_plan.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"actions": actions, "dry_run": dry, "evidence": evidence}, indent=2) + "\n"
    )
    logger.info("Plan written %s", out)

    if dry:
        logger.info("DRY RUN — no orders (pass --execute-paper to submit paper closes)")
        return 0

    n = execute_actions(client, actions, dry_run=False)
    logger.info("Submitted %s close orders", n)
    return 0 if n else 1


if __name__ == "__main__":
    raise SystemExit(main())
