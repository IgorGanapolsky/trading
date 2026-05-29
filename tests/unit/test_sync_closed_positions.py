"""Tests for scripts/sync_closed_positions.py.

Focus: surfacing singleton SIMPLE closes that the legacy pairing logic
drops because they carry no `position_intent` and cannot form a 4-leg
signature. Without this gap being visible, the paired ledger under-reports
realized P/L by ~$2.6K (broker truth -$6,570 vs ledger -$3,958), which
in turn corrupts the win-rate / expectancy / PF inputs that feed
`.claude/rules/kill-criteria.md`.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import sync_closed_positions as scp


def _option_symbol(expiry_yymmdd: str, kind: str, strike: int) -> str:
    # SPY + YYMMDD + C/P + strike padded to 8 digits, strike encoded * 1000
    strike_raw = f"{strike * 1000:08d}"
    return f"SPY{expiry_yymmdd}{kind}{strike_raw}"


def _make_leg(symbol: str, side: str, qty: int, price: float, intent: str) -> dict:
    return {
        "id": f"leg-{symbol}-{side}",
        "symbol": symbol,
        "side": side,
        "qty": str(qty),
        "filled_qty": str(qty),
        "filled_avg_price": str(price),
        "position_intent": intent,
        "status": "filled",
    }


def _make_parent_open(filled_at: str, expiry: str, *, order_id: str) -> dict:
    # SPY IC entry: SELL put 540, BUY put 530, SELL call 600, BUY call 610
    legs = [
        _make_leg(_option_symbol(expiry, "P", 540), "SELL", 1, 2.00, "sell_to_open"),
        _make_leg(_option_symbol(expiry, "P", 530), "BUY", 1, 1.00, "buy_to_open"),
        _make_leg(_option_symbol(expiry, "C", 600), "SELL", 1, 2.00, "sell_to_open"),
        _make_leg(_option_symbol(expiry, "C", 610), "BUY", 1, 1.00, "buy_to_open"),
    ]
    return {
        "id": order_id,
        "symbol": "SPY",
        "side": "sell",
        "qty": "1",
        "price": "2.00",
        "filled_at": filled_at,
        "status": "filled",
        "order_class": "mleg",
        "position_intent": "",
        "legs": legs,
    }


def _make_parent_close(filled_at: str, expiry: str, *, order_id: str) -> dict:
    # Closing the IC: opposite sides, intent=*_to_close
    legs = [
        _make_leg(_option_symbol(expiry, "P", 540), "BUY", 1, 1.00, "buy_to_close"),
        _make_leg(_option_symbol(expiry, "P", 530), "SELL", 1, 0.50, "sell_to_close"),
        _make_leg(_option_symbol(expiry, "C", 600), "BUY", 1, 1.00, "buy_to_close"),
        _make_leg(_option_symbol(expiry, "C", 610), "SELL", 1, 0.50, "sell_to_close"),
    ]
    return {
        "id": order_id,
        "symbol": "SPY",
        "side": "buy",
        "qty": "1",
        "price": "1.00",
        "filled_at": filled_at,
        "status": "filled",
        "order_class": "mleg",
        "position_intent": "",
        "legs": legs,
    }


def _make_singleton_close(
    filled_at: str, expiry: str, *, order_id: str, side: str, qty: int, price: float
) -> dict:
    """A SIMPLE close row with NO `position_intent` and NO legs — the exact
    shape that the legacy logic silently dropped."""
    return {
        "id": order_id,
        "symbol": _option_symbol(expiry, "P", 540),
        "side": side,
        "qty": str(qty),
        "price": str(price),
        "filled_at": filled_at,
        "status": "filled",
        "order_class": "simple",
        "position_intent": "",
        "legs": [],
    }


def test_unpaired_singletons_surface_in_stats_with_cohort_filter():
    """Build a broker history with:
      1. A clean 4-leg IC (open + close) that DOES pair.
      2. A SIMPLE singleton close AFTER 2026-04-09 (cohort window).
      3. A SIMPLE singleton close BEFORE 2026-04-09 (pre-cohort).

    Assert:
      - The paired IC is captured (paired ledger entry exists).
      - `unpaired_realized_pnl` includes BOTH singletons.
      - `unpaired_in_cohort_pnl` includes ONLY the post-cohort singleton.
    """
    trade_history = [
        _make_parent_open("2026-04-15T14:00:00Z", "260516", order_id="parent-open-1"),
        _make_parent_close("2026-04-16T15:00:00Z", "260516", order_id="parent-close-1"),
        # Singleton AFTER cohort start (2026-04-09): BUY to close at $0.75
        # signed_cash = -1 * 0.75 * 100 = -$75
        _make_singleton_close(
            "2026-04-10T14:30:00Z",
            "260417",
            order_id="single-post-cohort",
            side="buy",
            qty=1,
            price=0.75,
        ),
        # Singleton BEFORE cohort start: SELL at $0.50, signed_cash = +$50
        _make_singleton_close(
            "2026-03-25T14:30:00Z",
            "260327",
            order_id="single-pre-cohort",
            side="sell",
            qty=1,
            price=0.50,
        ),
    ]

    # Run the pairing pipeline directly (no I/O).
    paired = scp._pair_closed_trades_from_inventory(trade_history)
    # The clean IC should pair
    assert len(paired) == 1, f"expected 1 paired IC, got {len(paired)}: {paired}"
    paired_trade = paired[0]
    assert paired_trade["status"] == "closed"
    assert paired_trade["strategy"] == "iron_condor"

    # Verify exit order_ids on the paired trade do NOT include singletons
    exit_ids = set(paired_trade.get("order_ids", {}).get("exit") or [])
    assert "single-post-cohort" not in exit_ids
    assert "single-pre-cohort" not in exit_ids

    # Now compute unpaired-singleton stats
    unpaired = scp._compute_unpaired_singleton_pnl(trade_history, paired)

    # Both singletons should appear in unpaired_realized_pnl: -75 + 50 = -25
    assert unpaired["unpaired_order_count"] == 2
    assert unpaired["unpaired_realized_pnl"] == -25.0, unpaired

    # Only the post-cohort singleton should appear in unpaired_in_cohort_pnl
    assert unpaired["unpaired_in_cohort_pnl"] == -75.0, unpaired
    assert unpaired["unpaired_cohort_start"] == "2026-04-09"


def test_reverse_lookup_promotes_singleton_when_open_lot_matches():
    """When a SIMPLE close row's symbol+side+qty match an open parent-lot's
    expected_close_leg, the reverse-lookup fallback should promote it from
    'dropped' to 'paired'."""
    expiry = "260516"
    open_row = _make_parent_open(
        "2026-04-15T14:00:00Z", expiry, order_id="parent-open-rev"
    )
    # SIMPLE close of all 4 legs with no position_intent — must be matched
    # via reverse-lookup against the open lot's expected_close_legs.
    singleton_closes = [
        _make_singleton_close_for_symbol(
            "2026-04-16T15:00:00Z",
            symbol=_option_symbol(expiry, "P", 540),
            order_id="rev-p540",
            side="buy",
            qty=1,
            price=1.00,
        ),
        _make_singleton_close_for_symbol(
            "2026-04-16T15:00:01Z",
            symbol=_option_symbol(expiry, "P", 530),
            order_id="rev-p530",
            side="sell",
            qty=1,
            price=0.50,
        ),
        _make_singleton_close_for_symbol(
            "2026-04-16T15:00:02Z",
            symbol=_option_symbol(expiry, "C", 600),
            order_id="rev-c600",
            side="buy",
            qty=1,
            price=1.00,
        ),
        _make_singleton_close_for_symbol(
            "2026-04-16T15:00:03Z",
            symbol=_option_symbol(expiry, "C", 610),
            order_id="rev-c610",
            side="sell",
            qty=1,
            price=0.50,
        ),
    ]
    trade_history = [open_row, *singleton_closes]

    paired = scp._pair_closed_trades_from_inventory(trade_history)
    # The reverse-lookup should have rescued the 4 singleton closes into a
    # paired IC.
    assert len(paired) == 1, f"expected reverse-lookup to pair IC, got {paired}"


def _make_singleton_close_for_symbol(
    filled_at: str, *, symbol: str, order_id: str, side: str, qty: int, price: float,
    client_order_id: str = "",
) -> dict:
    return {
        "id": order_id,
        "symbol": symbol,
        "side": side,
        "qty": str(qty),
        "price": str(price),
        "filled_at": filled_at,
        "status": "filled",
        "order_class": "simple",
        "position_intent": "",
        "client_order_id": client_order_id,
        "legs": [],
    }


def test_stamped_client_order_id_pairs_without_reverse_lookup():
    """LL-354 contract test: when WE stamp `client_order_id=IC-CLOSE-*-*`
    at submission time, `_close_inventory` must promote SIMPLE singleton
    rows BEFORE the reverse-lookup fallback fires, and tag them with
    `alpaca_simple_close_client_order_id`. Crucially, the pairing must
    succeed even with NO `expected_close_index` (i.e. without the
    reverse-lookup heuristic having anything to match against).
    """
    expiry = "260516"
    open_row = _make_parent_open(
        "2026-04-15T14:00:00Z", expiry, order_id="parent-open-stamp"
    )
    # All 4 closes carry our stamped client_order_id. Intents:
    #   SP=short put close -> BPS, LP=long put close -> BPL
    #   SC=short call close -> BCS, LC=long call close -> BCL
    singleton_closes = [
        _make_singleton_close_for_symbol(
            "2026-04-16T15:00:00Z",
            symbol=_option_symbol(expiry, "P", 540),
            order_id="stamp-p540",
            side="buy",
            qty=1,
            price=1.00,
            client_order_id="IC-CLOSE-BPS-SP-1748549812345678901",
        ),
        _make_singleton_close_for_symbol(
            "2026-04-16T15:00:01Z",
            symbol=_option_symbol(expiry, "P", 530),
            order_id="stamp-p530",
            side="sell",
            qty=1,
            price=0.50,
            client_order_id="IC-CLOSE-BPL-LP-1748549812345678902",
        ),
        _make_singleton_close_for_symbol(
            "2026-04-16T15:00:02Z",
            symbol=_option_symbol(expiry, "C", 600),
            order_id="stamp-c600",
            side="buy",
            qty=1,
            price=1.00,
            client_order_id="IC-CLOSE-BCS-SC-1748549812345678903",
        ),
        _make_singleton_close_for_symbol(
            "2026-04-16T15:00:03Z",
            symbol=_option_symbol(expiry, "C", 610),
            order_id="stamp-c610",
            side="sell",
            qty=1,
            price=0.50,
            client_order_id="IC-CLOSE-BCL-LC-1748549812345678904",
        ),
    ]
    trade_history = [open_row, *singleton_closes]

    # Call _close_inventory WITHOUT expected_close_index so we prove the
    # client_order_id path is what's doing the work — not reverse-lookup.
    inventory = scp._close_inventory(trade_history, expected_close_index=None)

    # All 4 singleton closes must land in the inventory, each tagged with
    # the stamped-CID source.
    sources = [
        fill["source"]
        for fills in inventory.values()
        for fill in fills
        if "alpaca" in fill.get("source", "")
    ]
    assert sources, f"no inventory rows produced: {inventory}"
    assert all(
        s == "alpaca_simple_close_client_order_id" for s in sources
    ), f"expected all closes to be stamped-CID sourced, got {sources}"
    assert len(sources) == 4, sources

    # End-to-end: the full pairing pipeline yields exactly one paired IC.
    paired = scp._pair_closed_trades_from_inventory(trade_history)
    assert len(paired) == 1, paired
