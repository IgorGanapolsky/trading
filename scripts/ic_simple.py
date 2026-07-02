#!/usr/bin/env python3
"""
Simple Iron Condor System — One file, one workflow, no complexity.

Entry: Real 15-delta strikes via Alpaca option chain, limit orders only.
Exit:  50% profit, 100% stop, 7 DTE. 4-hour minimum hold. MLEG close.
Guard: Net-credit required, $0.50 minimum, 1 IC per day, position limit 2.

This replaces: iron_condor_trader.py, iron_condor_guardian.py,
iron_condor_scanner.py, manage_iron_condor_positions.py, and 6 workflows.
"""

# Trunk/isort and Ruff disagree on local imports inside function scopes in this script.
# Keep the repo's commit-hook formatting and suppress only import-order diagnostics here.
# ruff: noqa: I001

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("ic_simple")

# ── Strategy Parameters (ML-adjustable) ──────────────────────────────────────
STRATEGY_PARAMS_FILE = Path(__file__).parent.parent / "data" / "strategy_params.json"


def _load_strategy_params() -> dict:
    """Load strategy params from ML-writable config. Falls back to defaults."""
    defaults = {
        "target_delta": 0.15,
        "wing_width": 5,  # validation hypothesis: no 10-wide wings
        "target_dte": 30,
        "min_dte": 30,  # CLAUDE.md mandate: 30 DTE minimum
        "max_dte": 45,
        "min_credit": 0.50,
        "profit_target": 0.50,
        "stop_loss": 1.0,
        "exit_dte": 7,
        "max_ic": 2,  # CLAUDE.md mandate: 2 ICs max
    }
    try:
        if STRATEGY_PARAMS_FILE.exists():
            data = json.loads(STRATEGY_PARAMS_FILE.read_text())
            params = data.get("params", {})
            merged = {**defaults, **params}
            if data.get("updated_by") != "seed":
                logger.info(
                    f"ML params loaded (by {data.get('updated_by', '?')}, confidence={data.get('confidence', 0):.2f})"
                )
            return merged
    except Exception as e:
        logger.debug(f"Strategy params load failed: {e}")
    return defaults


_SP = _load_strategy_params()
MAX_IC = _SP["max_ic"]
MIN_CREDIT = _SP["min_credit"]
MIN_HOLD_HOURS = 24  # Not ML-adjustable (safety). Research: <1h hold = 6.5% win, >1d = 50% win
PROFIT_TARGET = _SP["profit_target"]
STOP_LOSS = _SP["stop_loss"]
EXIT_DTE = _SP["exit_dte"]
WING_WIDTH = _SP["wing_width"]
TARGET_DELTA = _SP["target_delta"]
ENTRIES_FILE = Path(__file__).parent.parent / "data" / "ic_entries.json"
SYSTEM_STATE_FILE = Path(__file__).parent.parent / "data" / "system_state.json"
THOMPSON_MIN_CONFIDENCE = 0.40
MIN_ACCEPTABLE_SHORT_DELTA = 0.08
MAX_ACCEPTABLE_SHORT_DELTA = 0.22
FOMC_DATES = [
    "2026-01-28",
    "2026-03-18",
    "2026-05-06",
    "2026-06-17",
    "2026-07-29",
    "2026-09-16",
    "2026-11-04",
    "2026-12-16",
]


def _fomc_blackout_reason(as_of=None) -> str | None:
    """Return the FOMC announcement date when new entries are blocked."""
    from datetime import timedelta

    today = as_of or datetime.now().date()
    for fomc_str in FOMC_DATES:
        fomc_date = datetime.strptime(fomc_str, "%Y-%m-%d").date()
        if (fomc_date - timedelta(days=2)) <= today <= (fomc_date + timedelta(days=1)):
            return fomc_str
    return None


# ── Alpaca Client ────────────────────────────────────────────────────────────
def get_client():
    from alpaca.trading.client import TradingClient

    from src.utils.alpaca_client import get_alpaca_credentials

    api_key, secret = get_alpaca_credentials()
    if not api_key or not secret:
        raise RuntimeError("Alpaca credentials not found")
    return TradingClient(api_key, secret, paper=True)


def get_spy_price(client):
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockLatestQuoteRequest

    from src.utils.alpaca_client import get_alpaca_credentials

    api_key, secret = get_alpaca_credentials()
    data_client = StockHistoricalDataClient(api_key, secret)
    quote = data_client.get_stock_latest_quote(StockLatestQuoteRequest(symbol_or_symbols=["SPY"]))
    return (quote["SPY"].ask_price + quote["SPY"].bid_price) / 2


# ── Entry: Find and Place IC ────────────────────────────────────────────────
def find_opportunity(spy_price: float) -> dict | None:
    """Select strikes by real delta. Returns opportunity dict or None."""
    from src.markets.option_chain import select_strikes_by_delta

    selection = select_strikes_by_delta(
        underlying_price=spy_price,
        wing_width=WING_WIDTH,
        target_delta=TARGET_DELTA,
        target_dte=30,
        min_dte=30,  # CLAUDE.md mandate: 30 DTE minimum
        max_dte=45,
    )

    if selection.method != "live_delta":
        logger.warning(
            f"Strike selection method {selection.method!r} is not live_delta. "
            "Skip: validation trades require real delta provenance."
        )
        return None

    put_delta = abs(float(selection.put_delta or 0.0))
    call_delta = abs(float(selection.call_delta or 0.0))
    if not (
        MIN_ACCEPTABLE_SHORT_DELTA <= put_delta <= MAX_ACCEPTABLE_SHORT_DELTA
        and MIN_ACCEPTABLE_SHORT_DELTA <= call_delta <= MAX_ACCEPTABLE_SHORT_DELTA
    ):
        logger.warning(
            f"Live deltas outside validation band: put={put_delta:.3f}, call={call_delta:.3f}, "
            f"required={MIN_ACCEPTABLE_SHORT_DELTA:.2f}-{MAX_ACCEPTABLE_SHORT_DELTA:.2f}. Skip."
        )
        return None

    # Net credit = short premiums - long premiums (NOT just short bids)
    est_credit = selection.net_credit
    if est_credit <= 0:
        logger.warning(f"Non-positive net credit ${est_credit:.2f}. Skip.")
        return None

    if est_credit < MIN_CREDIT:
        logger.warning(f"Credit ${est_credit:.2f} < ${MIN_CREDIT:.2f} minimum. Skip.")
        return None

    # Wing-width validation. `select_strikes_by_delta` allows wings as narrow
    # as 50% of the requested width (src/markets/option_chain.py MIN_WING_PCT
    # = 0.5), and silently snaps to the nearest chain strike. That can produce
    # asymmetric wings (e.g., $10 call wing + $5 put wing) which break the
    # max-loss calculation downstream (max_loss = (wing_width - credit) × 100
    # assumes symmetric wings) and corrupt the GRPO learning signal — wings
    # are not persisted with the lesson so the learner conflates $5- and
    # $10-wide trades. Per .claude/rules/kill-criteria.md the 30-trade
    # validation cohort must use "one profile only", which means uniform
    # WING_WIDTH. Reject any selection whose wings don't match exactly.
    put_wing = round(selection.short_put - selection.long_put, 2)
    call_wing = round(selection.long_call - selection.short_call, 2)
    if put_wing != WING_WIDTH or call_wing != WING_WIDTH:
        logger.warning(
            f"Wing-width contract violated: put_wing=${put_wing}, "
            f"call_wing=${call_wing}, required=${WING_WIDTH}. Skip "
            "(asymmetric or narrow wings change the risk profile and "
            "corrupt validation-cohort statistics)."
        )
        return None

    logger.info(
        f"Opportunity: SP={selection.short_put} SC={selection.short_call} "
        f"method={selection.method} credit=${est_credit:.2f} "
        f"put_delta={selection.put_delta:.3f} call_delta={selection.call_delta:.3f} "
        f"wings=${put_wing}/${call_wing}"
    )

    return {
        "expiry": selection.expiry,
        "long_put": selection.long_put,
        "short_put": selection.short_put,
        "short_call": selection.short_call,
        "long_call": selection.long_call,
        "put_wing": put_wing,
        "call_wing": call_wing,
        "est_credit": est_credit,
        "method": selection.method,
        "put_delta": selection.put_delta,
        "call_delta": selection.call_delta,
        "target_delta": TARGET_DELTA,
    }


def place_ic(client, opp: dict) -> str | None:
    """Submit limit MLEG order. Returns order ID or None."""
    from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
    from alpaca.trading.requests import LimitOrderRequest, OptionLegRequest

    from src.safety.mandatory_trade_gate import safe_submit_order
    from src.utils.order_intent import build_client_order_id

    expiry_yymmdd = opp["expiry"].replace("-", "")[2:]

    def sym(strike, opt_type):
        return f"SPY{expiry_yymmdd}{opt_type}{int(strike * 1000):08d}"

    legs = [
        OptionLegRequest(symbol=sym(opp["long_put"], "P"), side=OrderSide.BUY, ratio_qty=1),
        OptionLegRequest(symbol=sym(opp["short_put"], "P"), side=OrderSide.SELL, ratio_qty=1),
        OptionLegRequest(symbol=sym(opp["short_call"], "C"), side=OrderSide.SELL, ratio_qty=1),
        OptionLegRequest(symbol=sym(opp["long_call"], "C"), side=OrderSide.BUY, ratio_qty=1),
    ]

    limit_credit = round(opp["est_credit"] - 0.05, 2)
    if limit_credit < MIN_CREDIT:
        limit_credit = MIN_CREDIT

    # Price-walking: start at mid, walk $0.05 worse per attempt, up to $0.20 max concession
    # Industry standard: Option Alpha SmartPricing uses 4 levels at 10-15s each
    WALK_INCREMENT = 0.05
    MAX_WALK = 0.20
    WALK_WAIT_SECONDS = 20

    order_id = None
    filled = False
    fill_price: float | None = None
    walk_total = 0.0

    while walk_total <= MAX_WALK and not filled:
        current_credit = round(limit_credit - walk_total, 2)
        if current_credit < MIN_CREDIT:
            logger.warning(f"Price walk would drop below ${MIN_CREDIT:.2f} min. Stopping.")
            break

        logger.info(f"MLEG limit order: credit >= ${current_credit:.2f} (walk ${walk_total:.2f})")

        try:
            # LL-354: stamp OPEN-IC on the parent so the paired ledger can
            # identify it without relying on broker position_intent.
            order = safe_submit_order(
                client,
                LimitOrderRequest(
                    qty=1,
                    order_class=OrderClass.MLEG,
                    legs=legs,
                    time_in_force=TimeInForce.DAY,
                    limit_price=round(-current_credit, 2),
                    client_order_id=build_client_order_id("OPEN", "IC"),
                ),
                strategy="iron_condor",
            )
        except Exception as submit_err:
            # Log full error for debugging 422s from Alpaca
            resp_body = getattr(getattr(submit_err, "response", None), "text", "")
            if not resp_body:
                cause = getattr(submit_err, "__cause__", None)
                resp_body = getattr(getattr(cause, "response", None), "text", "")
            leg_symbols = [str(leg.symbol) for leg in legs]
            logger.error(
                f"Order submission failed: {submit_err}\n"
                f"  Legs: {leg_symbols}\n"
                f"  Limit: {round(-current_credit, 2)}\n"
                f"  Response: {resp_body}"
            )
            return None
        order_id = str(order.id)
        logger.info(f"Order {order_id}: {order.status}")

        filled, fill_price = _wait_for_fill(
            client, order_id, timeout_seconds=WALK_WAIT_SECONDS, poll_interval=5
        )
        if not filled:
            try:
                client.cancel_order_by_id(order_id)
            except Exception:
                pass
            walk_total = round(walk_total + WALK_INCREMENT, 2)

    if not filled:
        logger.warning(f"Price walk exhausted (${MAX_WALK:.2f} concession). No fill.")
        return None

    # Save entry data. Persist the *actual* fill credit so downstream profit-
    # target and stop-loss thresholds key off what the broker filled, not the
    # pre-walk estimate. Falls back to est_credit only if the broker did not
    # report a filled_avg_price for some reason.
    persisted_credit = fill_price if fill_price is not None else opp["est_credit"]
    if fill_price is not None and abs(fill_price - opp["est_credit"]) >= 0.05:
        logger.info(
            f"Persisted credit ${persisted_credit:.2f} differs from estimate "
            f"${opp['est_credit']:.2f} by ${persisted_credit - opp['est_credit']:+.2f} "
            "(price-walk concession)."
        )
    entries = _load_entries()
    entry_key = f"IC_{expiry_yymmdd}"
    # Persist entry timestamps as offset-aware UTC ISO strings. Naive local-
    # time writes produced mixed tz formats in data/ic_entries.json. The
    # reader's `.replace(tzinfo=None)` discarded (not converted) the offset,
    # so hold-time math drifted by the host-vs-entry tz offset (hours),
    # silently violating MIN_HOLD_HOURS=24.
    _now_utc_iso = datetime.now(timezone.utc).isoformat()
    entries[entry_key] = {
        "credit": persisted_credit,
        "date": _now_utc_iso,
        "entry_time": _now_utc_iso,
        "order_id": str(order.id),
        "signature": (
            f"SPY_{opp['expiry']}_"
            f"P{int(opp['long_put'])}-{int(opp['short_put'])}_"
            f"C{int(opp['short_call'])}-{int(opp['long_call'])}"
        ),
        "selection_method": opp.get("method"),
        "strike_selection_method": opp.get("method"),
        "put_delta": opp.get("put_delta"),
        "call_delta": opp.get("call_delta"),
        "target_delta": opp.get("target_delta", TARGET_DELTA),
        "validation_phase": True,
        "profile_name": "spy-core",
        "quantity": 1,
        "strikes": {
            "short_put": opp["short_put"],
            "short_call": opp["short_call"],
            "long_put": opp["long_put"],
            "long_call": opp["long_call"],
        },
    }
    _save_entries(entries)

    return str(order.id)


# ── Exit: Check and Close Positions ──────────────────────────────────────────
def check_exits(client):
    """Check all open ICs for exit conditions."""
    positions = client.get_all_positions()
    if not positions:
        logger.info("No positions.")
        return

    # Group by expiry
    ics = {}
    for pos in positions:
        sym = pos.symbol
        if len(sym) <= 10:
            continue
        expiry = sym[3:9]
        if expiry not in ics:
            ics[expiry] = []
        ics[expiry].append(
            {
                "symbol": sym,
                "qty": int(float(pos.qty)),
                "entry": float(pos.avg_entry_price),
                "current": float(pos.current_price)
                if hasattr(pos, "current_price")
                else float(pos.avg_entry_price),
                "type": "put" if "P" in sym[9:10] else "call",
            }
        )

    entries = _load_entries()

    for expiry, legs in ics.items():
        # Validate: need exactly 4 legs, 2P+2C, 2 short+2 long
        n_puts = sum(1 for leg in legs if leg["type"] == "put")
        n_calls = sum(1 for leg in legs if leg["type"] == "call")
        n_short = sum(1 for leg in legs if leg["qty"] < 0)
        n_long = sum(1 for leg in legs if leg["qty"] > 0)

        if not (n_puts == 2 and n_calls == 2 and n_short == 2 and n_long == 2):
            logger.warning(
                f"IC {expiry}: incomplete ({n_puts}P {n_calls}C {n_short}S {n_long}L). Skip."
            )
            continue

        # Get entry credit
        entry_key = f"IC_{expiry}"
        has_entry_record = entry_key in entries
        if has_entry_record:
            entry_credit = entries[entry_key]["credit"]
            entry_date = entries[entry_key].get("date")
        else:
            # Estimate from positions
            short_prem = sum(leg["entry"] for leg in legs if leg["qty"] < 0)
            long_prem = sum(leg["entry"] for leg in legs if leg["qty"] > 0)
            entry_credit = short_prem - long_prem
            entry_date = None
            if entry_credit <= 0:
                logger.warning(f"IC {expiry}: non-positive credit ${entry_credit:.2f}. Skip.")
                continue

        # Compute DTE first — the failsafe (dte <= 1) and 7DTE exits must NEVER
        # be suppressed by the MIN_HOLD_HOURS gate. An IC opened intraday with
        # short DTE can hit assignment risk before 24h elapse; the comment at
        # the exit-checks block (below) explicitly promises "DTE failsafe first
        # — always close expiring positions," so DTE-driven exits short-circuit
        # the hold window.
        from datetime import date as date_type

        exp_date = date_type(2000 + int(expiry[:2]), int(expiry[2:4]), int(expiry[4:6]))
        dte = (exp_date - date_type.today()).days
        dte_forces_exit = dte <= EXIT_DTE

        # Minimum holding period — MUST hold to allow theta decay, EXCEPT when
        # the DTE failsafe or 7DTE rule would otherwise exit. Use tz-aware
        # UTC arithmetic so an offset-aware writer + naive-local reader can't
        # silently produce a multi-hour skew. Legacy naive entries are
        # normalized to UTC; new writes are already offset-aware UTC.
        if not dte_forces_exit:
            if entry_date:
                try:
                    entry_dt = datetime.fromisoformat(entry_date)
                    if entry_dt.tzinfo is None:
                        entry_dt = entry_dt.astimezone(timezone.utc)
                    else:
                        entry_dt = entry_dt.astimezone(timezone.utc)
                    hours = (datetime.now(timezone.utc) - entry_dt).total_seconds() / 3600
                    if hours < MIN_HOLD_HOURS:
                        logger.info(f"IC {expiry}: held {hours:.1f}h < {MIN_HOLD_HOURS}h. Hold.")
                        continue
                except (ValueError, TypeError):
                    logger.warning(
                        f"IC {expiry}: unparseable entry_date '{entry_date}'. Hold (safety)."
                    )
                    continue
            else:
                # Unknown entry date — hold by default (don't exit blind)
                logger.warning(f"IC {expiry}: no entry_date recorded. Hold (safety default).")
                continue

        # Calculate P/L
        contract_count = max(abs(leg["qty"]) for leg in legs)
        current_value = sum(
            (-leg["current"] if leg["qty"] < 0 else leg["current"]) * abs(leg["qty"]) * 100
            for leg in legs
        )
        pnl = entry_credit * contract_count * 100 + current_value
        max_profit = entry_credit * contract_count * 100

        logger.info(
            f"IC {expiry}: DTE={dte} P/L=${pnl:+.2f} "
            f"(credit=${entry_credit:.2f}x{contract_count} max=${max_profit:.2f})"
        )

        # Exit checks (DTE failsafe first — always close expiring positions)
        reason = None
        if dte <= 1:
            reason = f"FAILSAFE: DTE={dte} (expiring — assignment/pin risk)"
        elif dte <= EXIT_DTE:
            reason = f"DTE={dte} <= {EXIT_DTE}"
        elif pnl >= max_profit * PROFIT_TARGET:
            reason = f"PROFIT: ${pnl:.2f} >= ${max_profit * PROFIT_TARGET:.2f}"
        elif pnl <= -(max_profit * STOP_LOSS):
            reason = f"STOP: ${pnl:.2f} <= -${max_profit * STOP_LOSS:.2f}"

        if reason:
            logger.warning(f"EXIT IC {expiry}: {reason}")
            _close_ic(client, legs, contract_count)
            # Drop the entry record so subsequent check_exits runs (before the
            # broker actually fills the close MLEG) don't see a stale key and
            # re-emit duplicate _record_lesson / _update_thompson updates. If
            # the close limit fails to fill and the position lingers, the next
            # run hits the estimate-from-positions path which is guarded by
            # has_entry_record below.
            if has_entry_record:
                entries.pop(entry_key, None)
                _save_entries(entries)
            # Only record a lesson + update Thompson when we had an
            # authoritative entry record. Estimated-credit lessons would
            # corrupt the learning signal with the wrong reference point.
            if has_entry_record:
                _record_lesson(expiry, entry_credit, pnl, reason, dte, contract_count)
                _update_thompson("WIN" if pnl > 0 else "LOSS")
            else:
                logger.warning(
                    f"IC {expiry}: exit triggered without entry record — "
                    "skipping lesson/Thompson update (estimate path)."
                )
        else:
            logger.info(
                f"IC {expiry}: HOLD. Target=${max_profit * PROFIT_TARGET:.2f} Stop=-${max_profit * STOP_LOSS:.2f}"
            )


def _close_ic(client, legs: list[dict], qty: int):
    """Close IC with MLEG limit order. Fallback to individual legs."""
    from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
    from alpaca.trading.requests import (
        LimitOrderRequest,
        MarketOrderRequest,
        OptionLegRequest,
    )

    from src.safety.mandatory_trade_gate import safe_submit_order
    from src.utils.order_intent import build_client_order_id

    def _leg_intent_tag(symbol: str, qty: int) -> tuple[str, str]:
        """LL-354: map a leg about to be CLOSED to (INTENT, LEG_TAG).
        BPS/BPL = bull put short/long; BCS/BCL = bear call short/long."""
        # OCC: SPY{YYMMDD}{C|P}{NNNNNNNN}. C/P sits at index -9 (one char
        # before the 8-digit strike). Default to "P" if we can't read it.
        opt_type = symbol[-9] if len(symbol) >= 9 else "P"
        is_short = qty < 0
        if opt_type == "P":
            return ("BPS", "SP") if is_short else ("BPL", "LP")
        return ("BCS", "SC") if is_short else ("BCL", "LC")

    # Calculate current debit
    current_debit = abs(sum(leg["current"] * (1 if leg["qty"] < 0 else -1) for leg in legs))
    limit_debit = round(current_debit + 0.10, 2)

    option_legs = [
        OptionLegRequest(
            symbol=leg["symbol"],
            side=OrderSide.BUY if leg["qty"] < 0 else OrderSide.SELL,
            ratio_qty=1,
        )
        for leg in legs
    ]

    try:
        order = safe_submit_order(
            client,
            LimitOrderRequest(
                qty=qty,
                order_class=OrderClass.MLEG,
                legs=option_legs,
                time_in_force=TimeInForce.DAY,
                limit_price=round(limit_debit, 2),
                client_order_id=build_client_order_id("CLOSE", "IC"),
            ),
            strategy="iron_condor",
        )
        logger.info(f"MLEG close: {order.id} @ ${limit_debit:.2f} debit")
    except Exception as e:
        logger.warning(f"MLEG close failed ({e}). Individual leg fallback.")
        for leg in legs:
            try:
                side = OrderSide.BUY if leg["qty"] < 0 else OrderSide.SELL
                # LL-354: this is the singleton-SIMPLE-close path that the
                # paired ledger used to lose. Stamp role+intent+leg so
                # sync_closed_positions can pair authoritatively.
                intent, tag = _leg_intent_tag(str(leg["symbol"]), int(leg["qty"]))
                safe_submit_order(
                    client,
                    MarketOrderRequest(
                        symbol=leg["symbol"],
                        qty=abs(leg["qty"]),
                        side=side,
                        time_in_force=TimeInForce.DAY,
                        client_order_id=build_client_order_id("CLOSE", intent, tag),
                    ),
                    strategy="iron_condor",
                )
            except Exception as le:
                logger.error(f"Failed to close {leg['symbol']}: {le}")


# ── Learning: RAG + Trade Journal + Stats ────────────────────────────────────

JOURNAL_FILE = Path(__file__).parent.parent / "data" / "trade_journal.jsonl"
IC_STATS_FILE = Path(__file__).parent.parent / "data" / "ic_stats.json"
TRADE_LEDGER_FILE = Path(__file__).parent.parent / "data" / "trades.json"
LESSONS_DIR = Path(__file__).parent.parent / "rag_knowledge" / "lessons_learned"  # Primary corpus


def _record_lesson(expiry: str, credit: float, pnl: float, reason: str, dte: int, qty: int):
    """Record trade outcome to journal + RAG after every close."""
    outcome = "WIN" if pnl > 0 else "LOSS"
    pnl_pct = (pnl / (credit * qty * 100)) * 100 if credit > 0 else 0

    # 0. Compute composite reward (ML training signal)
    reward_data = {}
    try:
        from src.ml.reward import compute_trade_reward

        max_loss = WING_WIDTH * 100 - credit * qty * 100
        reward_data = compute_trade_reward(
            pnl=pnl,
            credit=credit,
            max_loss=max_loss,
            dte_at_exit=dte,
        )
        logger.info(
            f"Reward: {reward_data['total_reward']:+.3f} "
            f"(return={reward_data['components']['return']:+.3f} "
            f"downside={reward_data['components']['downside']:+.3f})"
        )
    except Exception as e:
        logger.debug(f"Reward computation skipped: {e}")

    # 1. Trade journal (append-only JSONL)
    entry = {
        "timestamp": datetime.now().isoformat(),
        "expiry": expiry,
        "credit_per_share": credit,
        "qty": qty,
        "pnl": round(pnl, 2),
        "pnl_pct": round(pnl_pct, 1),
        "outcome": outcome,
        "exit_reason": reason,
        "dte_at_exit": dte,
        "composite_reward": reward_data.get("total_reward", 0),
        "reward_components": reward_data.get("components", {}),
    }
    try:
        JOURNAL_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(JOURNAL_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")
        logger.info(f"Journal: {outcome} ${pnl:+.2f} ({pnl_pct:+.1f}%) | {reason}")
    except Exception as e:
        logger.warning(f"Failed to write journal: {e}")

    # 2. RAG lesson (one markdown file per trade)
    lesson_id = f"IC_{expiry}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    lesson = f"""# Trade Exit: {outcome} ${pnl:+.2f}

- **Expiry**: {expiry}
- **Credit**: ${credit:.2f}/share x {qty} contracts
- **P/L**: ${pnl:+.2f} ({pnl_pct:+.1f}%)
- **Exit Reason**: {reason}
- **DTE at Exit**: {dte}
- **Date**: {datetime.now().strftime("%Y-%m-%d %H:%M")}

## Lesson
{"Position hit profit target — theta decay worked as expected." if "PROFIT" in reason else ""}{"Position hit stop loss — market moved against us." if "STOP" in reason else ""}{"Exited at DTE threshold to avoid gamma risk." if "DTE" in reason else ""}
"""
    try:
        LESSONS_DIR.mkdir(parents=True, exist_ok=True)
        (LESSONS_DIR / f"{lesson_id}.md").write_text(lesson)
        logger.info(f"RAG lesson saved: {lesson_id}")
        # Refresh singleton so next query in this session sees the new lesson
        try:
            from src.rag.lessons_search import get_lessons_search

            get_lessons_search(refresh=True)
        except Exception:
            pass
    except Exception as e:
        logger.warning(f"Failed to write RAG lesson: {e}")

    # 3. Update cumulative stats
    _update_stats(entry)


def _update_stats(trade: dict):
    """Update running win rate and P/L stats."""
    try:
        stats = (
            json.loads(IC_STATS_FILE.read_text())
            if IC_STATS_FILE.exists()
            else {
                "total": 0,
                "wins": 0,
                "losses": 0,
                "total_pnl": 0,
                "avg_win": 0,
                "avg_loss": 0,
                "win_pnls": [],
                "loss_pnls": [],
            }
        )
    except Exception:
        stats = {
            "total": 0,
            "wins": 0,
            "losses": 0,
            "total_pnl": 0,
            "avg_win": 0,
            "avg_loss": 0,
            "win_pnls": [],
            "loss_pnls": [],
        }

    stats["total"] += 1
    stats["total_pnl"] = round(stats["total_pnl"] + trade["pnl"], 2)

    if trade["pnl"] > 0:
        stats["wins"] += 1
        stats["win_pnls"].append(trade["pnl"])
        stats["avg_win"] = round(sum(stats["win_pnls"]) / len(stats["win_pnls"]), 2)
    else:
        stats["losses"] += 1
        stats["loss_pnls"].append(trade["pnl"])
        stats["avg_loss"] = round(sum(stats["loss_pnls"]) / len(stats["loss_pnls"]), 2)

    stats["win_rate"] = round(stats["wins"] / stats["total"] * 100, 1) if stats["total"] > 0 else 0
    stats["profit_factor"] = (
        round(abs(sum(stats["win_pnls"])) / abs(sum(stats["loss_pnls"])), 2)
        if stats["loss_pnls"] and sum(stats["loss_pnls"]) != 0
        else 999.0
    )

    IC_STATS_FILE.write_text(json.dumps(stats, indent=2))
    logger.info(
        f"Stats: {stats['total']} trades | {stats['win_rate']}% win rate | "
        f"PF={stats['profit_factor']} | Total P/L=${stats['total_pnl']:+.2f}"
    )


# ── Report + Weekend Learning ────────────────────────────────────────────────


def _as_report_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_report_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _load_lifetime_ledger_summary() -> dict:
    """Load paired-trade lifetime stats so validation reports cannot overstate edge."""
    try:
        payload = json.loads(TRADE_LEDGER_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.debug(f"Lifetime ledger summary unavailable: {exc}")
        return {}

    stats = payload.get("stats", {}) if isinstance(payload, dict) else {}
    if not isinstance(stats, dict):
        return {}

    closed = _as_report_int(stats.get("closed_trades") or stats.get("total_trades"))
    wins = _as_report_int(stats.get("wins"))
    losses = _as_report_int(stats.get("losses"))
    win_rate = _as_report_float(stats.get("win_rate_pct"))
    profit_factor = _as_report_float(stats.get("profit_factor"))
    total_realized = _as_report_float(stats.get("total_realized_pnl", stats.get("total_pnl")))
    expectancy = round(total_realized / closed, 4) if closed else 0.0

    return {
        "closed_trades": closed,
        "wins": wins,
        "losses": losses,
        "win_rate_pct": win_rate,
        "profit_factor": profit_factor,
        "total_realized_pnl": total_realized,
        "expectancy_per_trade": expectancy,
    }


def _print_north_star_readiness_report(validation_total: int):
    ledger = _load_lifetime_ledger_summary()
    gate = _load_north_star_weekly_gate()
    if not ledger and not gate:
        return

    logger.info("")
    logger.info("NORTH STAR READINESS")
    logger.info(
        "Validation slice is not promotion evidence until it reaches 30 clean closed trades."
    )
    logger.info(f"Validation slice: {validation_total}/30 closed trades")

    if ledger:
        logger.info(
            "Lifetime ledger: "
            f"{ledger['closed_trades']} closed | "
            f"win_rate={ledger['win_rate_pct']:.2f}% | "
            f"PF={ledger['profit_factor']:.2f} | "
            f"expectancy=${ledger['expectancy_per_trade']:+.2f}/trade | "
            f"realized=${ledger['total_realized_pnl']:+,.2f}"
        )

    if gate:
        logger.info(
            "Gate state: "
            f"mode={gate.get('mode', 'unknown')} | "
            f"scale_allowed={bool(gate.get('scale_allowed'))} | "
            f"block_new_positions={bool(gate.get('block_new_positions'))}"
        )
        reason = str(gate.get("blocker_reason") or gate.get("reason") or "").strip()
        if reason:
            logger.info(f"Gate blocker: {reason}")


def _print_report():
    """Print full performance report from trade journal."""
    if not IC_STATS_FILE.exists():
        logger.info("No stats yet. Complete trades to build data.")
        _print_north_star_readiness_report(0)
        return

    stats = json.loads(IC_STATS_FILE.read_text())
    logger.info("=" * 60)
    logger.info("PERFORMANCE REPORT")
    logger.info("=" * 60)
    logger.info(f"Total trades:   {stats.get('total', 0)}")
    logger.info(f"Wins:           {stats.get('wins', 0)}")
    logger.info(f"Losses:         {stats.get('losses', 0)}")
    logger.info(f"Win rate:       {stats.get('win_rate', 0):.1f}%")
    logger.info(f"Profit factor:  {stats.get('profit_factor', 0):.2f}")
    logger.info(f"Closed P/L:     ${stats.get('total_pnl', 0):+,.2f}")
    logger.info(f"Avg win:        ${stats.get('avg_win', 0):+,.2f}")
    logger.info(f"Avg loss:       ${stats.get('avg_loss', 0):+,.2f}")

    needed = 30 - stats.get("total", 0)
    if needed > 0:
        logger.info(f"\nNeed {needed} more trades for statistical significance.")
    else:
        wr = stats.get("win_rate", 0)
        if wr >= 80:
            logger.info("\n80%+ win rate VALIDATED. Strategy is working.")
        elif wr >= 70:
            logger.info("\n70-80% win rate. Marginal — review delta selection.")
        else:
            logger.info(f"\n{wr}% win rate. Below target. Reassess strategy.")

    _print_north_star_readiness_report(stats.get("total", 0))

    # Print recent trades from journal
    if JOURNAL_FILE.exists():
        lines = JOURNAL_FILE.read_text().strip().split("\n")
        logger.info("\nLast 5 trades:")
        for line in lines[-5:]:
            trade = json.loads(line)
            logger.info(
                f"  {trade['expiry']} | {trade['outcome']} ${trade['pnl']:+.2f} "
                f"({trade['pnl_pct']:+.1f}%) | {trade['exit_reason']}"
            )


def _weekend_learn():
    """Weekend learning: analyze all closed trades, extract patterns, update strategy.

    Run this on Saturday/Sunday to review the week's performance.
    """
    logger.info("=" * 60)
    logger.info("WEEKEND LEARNING SESSION")
    logger.info("=" * 60)

    if not JOURNAL_FILE.exists():
        logger.info("No trade journal yet. Nothing to learn from.")
        return

    lines = JOURNAL_FILE.read_text().strip().split("\n")
    trades = [json.loads(line) for line in lines if line.strip()]

    if not trades:
        logger.info("No trades to analyze.")
        return

    # Analyze patterns
    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]

    logger.info(f"Total trades: {len(trades)}")
    logger.info(f"Wins: {len(wins)} | Losses: {len(losses)}")

    # Exit reason analysis
    exit_reasons = {}
    for trade in trades:
        reason_type = (
            "PROFIT"
            if "PROFIT" in trade["exit_reason"]
            else "STOP"
            if "STOP" in trade["exit_reason"]
            else "DTE"
            if "DTE" in trade["exit_reason"]
            else "OTHER"
        )
        if reason_type not in exit_reasons:
            exit_reasons[reason_type] = {"count": 0, "total_pnl": 0}
        exit_reasons[reason_type]["count"] += 1
        exit_reasons[reason_type]["total_pnl"] += trade["pnl"]

    logger.info("\nExit reason analysis:")
    for reason, data in exit_reasons.items():
        avg = data["total_pnl"] / data["count"] if data["count"] > 0 else 0
        logger.info(f"  {reason}: {data['count']} trades, avg P/L=${avg:+.2f}")

    # DTE analysis
    if trades:
        avg_dte = sum(t.get("dte_at_exit", 0) for t in trades) / len(trades)
        logger.info(f"\nAvg DTE at exit: {avg_dte:.1f}")

    # Generate weekly lesson
    lesson_file = LESSONS_DIR / f"weekly_{datetime.now().strftime('%Y%m%d')}.md"
    LESSONS_DIR.mkdir(parents=True, exist_ok=True)

    total_pnl = sum(t["pnl"] for t in trades)
    win_rate = len(wins) / len(trades) * 100 if trades else 0

    lesson = f"""# Weekly Review — {datetime.now().strftime("%Y-%m-%d")}

## Performance
- Trades: {len(trades)} ({len(wins)}W / {len(losses)}L)
- Win rate: {win_rate:.1f}%
- Total P/L: ${total_pnl:+.2f}

## Exit Analysis
"""
    for reason, data in exit_reasons.items():
        avg = data["total_pnl"] / data["count"] if data["count"] > 0 else 0
        lesson += f"- {reason}: {data['count']} trades, avg ${avg:+.2f}\n"

    lesson += f"""
## Recommendations
{"- Strategy validated at {win_rate:.0f}% win rate" if win_rate >= 80 else ""}{"- Win rate {win_rate:.0f}% below 80% target — consider widening delta or tightening stops" if win_rate < 80 and trades else ""}
{"- Need more data — only {len(trades)} trades so far" if len(trades) < 30 else ""}
"""
    lesson_file.write_text(lesson)
    logger.info(f"\nWeekly lesson saved: {lesson_file.name}")

    # Research: fetch latest IC strategy insights and save to RAG
    _research_strategies(win_rate, len(trades), total_pnl)


def _adjust_strategy_params(adjustments: dict, reason: str, source: str, confidence: float):
    """Write adjusted strategy parameters. Called by GRPO or research pipeline.

    Safety: only adjusts if confidence >= 0.7 and changes are within bounds.
    """
    # Pull canonical caps from trading_constants so ML adjustments cannot
    # silently breach .claude/CLAUDE.md policy. Falls back to defensive
    # defaults if the import path is broken.
    try:
        from src.core.trading_constants import (
            IRON_CONDOR_STOP_LOSS_MULTIPLIER,
            MAX_CONCURRENT_IRON_CONDORS,
        )

        canonical_max_ic = int(MAX_CONCURRENT_IRON_CONDORS)
        canonical_stop_loss = float(IRON_CONDOR_STOP_LOSS_MULTIPLIER)
    except ImportError:
        canonical_max_ic = 2
        canonical_stop_loss = 1.0

    BOUNDS = {
        "target_delta": (0.10, 0.25),  # Never go below 10-delta or above 25-delta
        "wing_width": (5, 15),  # $5-$15 wide
        "target_dte": (21, 60),  # 21-60 DTE
        "min_credit": (0.30, 2.00),  # Floor $0.30, cap $2.00
        "profit_target": (0.25, 0.75),  # 25-75% profit take
        # Stop-loss is canonical (1.0× credit). Allow a tighter stop down to
        # 0.75× but never relax beyond canonical — looser stops would let
        # losses run past the policy cap.
        "stop_loss": (0.75, canonical_stop_loss),
        "exit_dte": (3, 14),  # 3-14 DTE exit
        # max_ic upper bound is the canonical MAX_CONCURRENT_IRON_CONDORS
        # (currently 2). A previous bound of 4 silently allowed ML to double
        # the capital-at-risk envelope vs .claude/CLAUDE.md policy.
        "max_ic": (1, canonical_max_ic),
    }

    if confidence < 0.7:
        logger.info(f"Param adjustment skipped: confidence {confidence:.2f} < 0.70")
        return

    # Validate bounds
    safe_adjustments = {}
    for key, value in adjustments.items():
        if key in BOUNDS:
            lo, hi = BOUNDS[key]
            clamped = max(lo, min(hi, value))
            if clamped != value:
                logger.warning(f"Clamped {key}: {value} → {clamped} (bounds {lo}-{hi})")
            safe_adjustments[key] = clamped

    if not safe_adjustments:
        return

    try:
        data = json.loads(STRATEGY_PARAMS_FILE.read_text()) if STRATEGY_PARAMS_FILE.exists() else {}
        params = data.get("params", {})
        old_params = dict(params)
        params.update(safe_adjustments)
        data["params"] = params
        data["updated_at"] = datetime.now().isoformat()
        data["updated_by"] = source
        data["confidence"] = confidence
        data.setdefault("adjustments", []).append(
            {
                "timestamp": datetime.now().isoformat(),
                "source": source,
                "confidence": confidence,
                "reason": reason,
                "changes": {
                    k: {"old": old_params.get(k), "new": v} for k, v in safe_adjustments.items()
                },
            }
        )
        # Keep last 50 adjustments
        data["adjustments"] = data["adjustments"][-50:]
        STRATEGY_PARAMS_FILE.write_text(json.dumps(data, indent=2))
        logger.info(
            f"Strategy params adjusted by {source}: {safe_adjustments} (confidence={confidence:.2f})"
        )
    except Exception as e:
        logger.warning(f"Failed to write strategy params: {e}")


def _daily_learn():
    """Continuous learning: runs after every trading session (not just weekends).

    - Retrains GRPO model from latest closed trades
    - Researches one strategy topic based on current performance gaps
    - Updates stats and prints brief report
    """
    logger.info("\n--- DAILY LEARNING ---")

    # 1. GRPO retrain — OBSERVE ONLY during controlled experiment phase.
    # No param injection until 30 clean trades prove positive expectancy.
    # See .claude/rules/controlled-experiment.md
    try:
        from src.ml.grpo_trade_learner import GRPOTradeLearner

        learner = GRPOTradeLearner()
        result = learner.train()
        logger.info(f"GRPO retrain (observe only): {result}")
        # DISABLED: GRPO param injection blocked during validation phase.
        # The GRPO confidence formula (0.5 + trades/100) is count-based, not quality-based.
        # Training losses are diverging (-11 to -17), model is not converging.
    except Exception as e:
        logger.debug(f"GRPO retrain skipped: {e}")

    # 2. Quick strategy research (one query per session, saves to RAG)
    trade_count = 0
    win_rate = 0
    total_pnl = 0
    try:
        stats = json.loads(IC_STATS_FILE.read_text()) if IC_STATS_FILE.exists() else {}
        win_rate = stats.get("win_rate", 0)
        trade_count = stats.get("total", 0)
        total_pnl = stats.get("total_pnl", 0)
        _research_strategies(win_rate, trade_count, total_pnl)
    except Exception as e:
        logger.debug(f"Research skipped: {e}")

    # 3. Performance-based auto-adjustment (data-driven, not research-driven)
    if trade_count >= 10:
        _auto_adjust_from_performance(stats)

    # 4. Brief performance snapshot
    _print_report()


def _auto_adjust_from_performance(_stats: dict):
    """Adjust strategy params based on actual trade performance data.

    DISABLED during controlled experiment phase (Apr 2026).
    No parameter drift until 30 clean trades prove positive expectancy.
    See .claude/rules/controlled-experiment.md
    """
    logger.info("Auto-adjust DISABLED during controlled experiment phase.")


def _research_strategies(win_rate: float, trade_count: int, total_pnl: float):
    """Fetch iron condor strategy research from multiple sources, save to RAG.

    Sources (tried in order): DuckDuckGo API JSON, DuckDuckGo Lite HTML.
    Results are deduplicated and saved as a daily research note.
    """
    import re
    import urllib.parse
    import urllib.request

    # Rotate queries based on performance gaps
    queries = []
    if trade_count < 10:
        queries.append("iron condor SPY 15 delta fill rate MLEG limit order 2024 2025")
        queries.append("tastytrade iron condor entry frequency mechanical systematic")
    elif win_rate < 80:
        queries.append(f"iron condor improve win rate below {win_rate:.0f}% delta adjustment")
        queries.append("iron condor adjustment rolling strategy when tested")
    else:
        queries.append("iron condor scale position sizing $100K account management")
        queries.append("iron condor SPX vs SPY tax 1256 advantages scaling")

    # Pick one query per session (rotate by day)
    query = queries[datetime.now().timetuple().tm_yday % len(queries)]

    snippets = []
    try:
        # Try DuckDuckGo JSON API first (more structured)
        api_url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}&format=json&no_html=1&skip_disambig=1"
        req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            import json as _json

            data = _json.loads(resp.read().decode("utf-8"))
            if data.get("AbstractText"):
                snippets.append(data["AbstractText"][:300])
            for topic in data.get("RelatedTopics", [])[:5]:
                if isinstance(topic, dict) and topic.get("Text"):
                    snippets.append(topic["Text"][:200])
    except Exception:
        pass

    if len(snippets) < 3:
        # Fallback: DuckDuckGo Lite HTML
        try:
            url = f"https://lite.duckduckgo.com/lite/?q={urllib.parse.quote(query)}&kl=us-en"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
            html_snippets = re.findall(r'class="result-snippet">(.*?)</td>', html, re.DOTALL)
            if not html_snippets:
                html_snippets = re.findall(r"<td[^>]*>(.*?)</td>", html, re.DOTALL)
            for s in html_snippets[:5]:
                clean = re.sub(r"<[^>]+>", "", s).strip()
                if len(clean) > 30:
                    snippets.append(clean[:200])
        except Exception:
            pass

    # Deduplicate
    seen = set()
    unique = []
    for s in snippets:
        key = s[:50].lower()
        if key not in seen:
            seen.add(key)
            unique.append(s)

    if unique:
        research_file = LESSONS_DIR / f"research_{datetime.now().strftime('%Y%m%d')}.md"
        LESSONS_DIR.mkdir(parents=True, exist_ok=True)
        content = f"""# Strategy Research — {datetime.now().strftime("%Y-%m-%d")}

## Context
- Trade count: {trade_count}
- Win rate: {win_rate:.1f}%
- Total P/L: ${total_pnl:+.2f}
- Query: {query}

## Findings
"""
        for i, snippet in enumerate(unique, 1):
            content += f"\n{i}. {snippet}\n"

        content += f"""
## Auto-Analysis
- Trades needed for significance: {max(0, 30 - trade_count)}
- Current phase: {"validation" if trade_count < 30 else "scaling" if win_rate >= 80 else "optimization"}
- Priority: {"increase trade frequency" if trade_count < 10 else "improve win rate" if win_rate < 80 else "scale up"}
"""
        research_file.write_text(content)
        logger.info(f"Research saved: {research_file.name} ({len(unique)} findings)")
    else:
        logger.info("Research: no findings from web sources")


# ── Thompson Sampling ────────────────────────────────────────────────────────


def _get_thompson_confidence() -> float:
    """Sample from Thompson posterior. Returns confidence 0-1."""
    try:
        from src.ml.trade_confidence import TradeConfidenceModel

        model = TradeConfidenceModel()
        return model.sample_confidence(strategy="iron_condor", ticker="SPY")
    except Exception as e:
        logger.debug(f"Thompson sampling unavailable: {e}")
        return 0.0  # Fail-closed: block entry when model unavailable


def _load_north_star_weekly_gate() -> dict:
    try:
        data = json.loads(SYSTEM_STATE_FILE.read_text(encoding="utf-8"))
        gate = data.get("north_star_weekly_gate", {})
        return gate if isinstance(gate, dict) else {}
    except Exception as exc:
        logger.debug(f"North Star weekly gate load failed: {exc}")
        return {}


def _allows_controlled_paper_validation_entry() -> bool:
    gate = _load_north_star_weekly_gate()
    return (
        gate.get("mode") == "validation_reset"
        and bool(gate.get("allow_validation_entries"))
        and bool(gate.get("block_live_new_positions"))
    )


LOSING_EXPIRY_LOOKBACK_DAYS = 45


def _load_losing_expiries(
    trades_file: Path | None = None,
    *,
    now: datetime | None = None,
    lookback_days: int = LOSING_EXPIRY_LOOKBACK_DAYS,
) -> set[str]:
    """Return IC expiries that produced a closed loss within ``lookback_days``.

    The unbounded historical version of this filter blocked any new entry
    targeting an expiry date that had EVER produced a loss. With 30–45 DTE
    entries on SPY weeklies, future expiry dates routinely collide with
    expiry dates already in the historical loss set — so the rule
    permanently starved the validation cohort instead of preventing
    same-expiry re-entry within the active cohort. Restrict to losses
    whose ``exit_date`` (fall back to ``entry_date``) is within the last
    ``lookback_days`` days. Past expiries that have already passed cannot
    collide with new 30–45 DTE candidates anyway; cohorts older than the
    window are not "same expiry, same cohort" risk.
    """
    from datetime import timedelta

    path = trades_file or TRADE_LEDGER_FILE
    try:
        trades_data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception as exc:
        logger.debug(f"Re-entry check skipped: {exc}")
        return set()

    closed = trades_data.get("trades", []) if isinstance(trades_data, dict) else []
    cutoff = (now or datetime.now()).date() - timedelta(days=lookback_days)
    losing_expiries: set[str] = set()
    for trade in closed:
        if not isinstance(trade, dict):
            continue

        realized_raw = trade.get("realized_pnl", 0)
        try:
            realized_pnl = float(realized_raw)
        except (TypeError, ValueError):
            realized_pnl = 0.0

        outcome = str(trade.get("outcome", "")).strip().lower()
        if realized_pnl >= 0 and outcome != "loss":
            continue

        # Recency filter — drop losses older than the lookback window.
        ref_raw = str(trade.get("exit_date") or trade.get("entry_date") or "").strip()
        if not ref_raw:
            continue
        try:
            ref_date = datetime.fromisoformat(ref_raw.split("T")[0]).date()
        except ValueError:
            continue
        if ref_date < cutoff:
            continue

        legs = trade.get("legs")
        if isinstance(legs, dict):
            expiry = str(legs.get("expiry") or "").strip()
            if expiry:
                losing_expiries.add(expiry)
                continue

        signature = str(trade.get("signature") or "")
        parts = signature.split("_")
        if len(parts) >= 2 and parts[0] == "SPY" and parts[1]:
            losing_expiries.add(parts[1])

    return losing_expiries


def _should_skip_for_thompson(confidence: float) -> tuple[bool, str]:
    if confidence >= THOMPSON_MIN_CONFIDENCE:
        return False, (f"Thompson confidence {confidence:.3f} >= {THOMPSON_MIN_CONFIDENCE:.2f}")
    if _allows_controlled_paper_validation_entry():
        return False, (
            f"Thompson confidence {confidence:.3f} < {THOMPSON_MIN_CONFIDENCE:.2f}, "
            "but controlled paper validation entries are allowed; live/scaling remains blocked."
        )
    return True, (
        f"Thompson confidence {confidence:.3f} < {THOMPSON_MIN_CONFIDENCE:.2f} — skip entry"
    )


def _query_rag_before_entry(spy_price: float):
    """Query RAG for relevant lessons before entering a trade."""
    try:
        from src.rag.vector_store import query_lessons

        question = f"SPY iron condor entry at ${spy_price:.0f} lessons risks warnings"
        results = query_lessons(question, top_k=3)
        if results:
            logger.info(f"RAG: {len(results)} relevant lessons found")
            for r in results:
                logger.info(f"  [{r['source']}] {r['content'][:100]}... (score={r['score']:.2f})")
        else:
            logger.info("RAG: no relevant lessons")
    except Exception as e:
        logger.debug(f"RAG query skipped: {e}")


def _update_thompson(outcome: str):
    """Update Thompson model after trade close. outcome: 'WIN' or 'LOSS'."""
    try:
        from src.ml.trade_confidence import TradeConfidenceModel

        model = TradeConfidenceModel()
        model.record_trade_outcome(success=(outcome == "WIN"), strategy="iron_condor", ticker="SPY")
        posterior = model.get_posterior_mean(strategy="iron_condor", ticker="SPY")
        logger.info(f"Thompson updated: {outcome} → posterior mean={posterior:.3f}")
    except Exception as e:
        logger.debug(f"Thompson update failed: {e}")


# ── Helpers ──────────────────────────────────────────────────────────────────
def _thumbgate_matches(rule: dict) -> bool:
    """Check if a ThumbGate rule matches current conditions."""
    condition = rule.get("condition", {})
    # Example rule: {"condition": {"vix_above": 30}, "reason": "Don't enter when VIX > 30"}
    if "vix_above" in condition:
        try:
            from src.options.vix_monitor import VIXMonitor

            vix = VIXMonitor().get_current_vix()
            if vix > condition["vix_above"]:
                return True
        except Exception:
            pass
    if "day_of_week" in condition:
        if datetime.now().strftime("%A").lower() == condition["day_of_week"].lower():
            return True
    return False


def _load_entries() -> dict:
    if not ENTRIES_FILE.exists():
        return {}
    try:
        return json.loads(ENTRIES_FILE.read_text())
    except json.JSONDecodeError as exc:
        # File corruption is high-impact: a silently-empty entries dict means
        # check_exits cannot manage live legs (no 50%/stop/7DTE close) AND the
        # MAX_IC=2 gate counts zero, allowing a duplicate IC on top of the
        # orphaned position. Log loudly so the operator can investigate
        # rather than discovering corruption days later via missing exits.
        logger.error(
            f"ENTRIES FILE CORRUPT at {ENTRIES_FILE}: {exc}. "
            "Treating as empty — open positions WILL NOT be tracked. "
            "Restore from backup or re-derive from broker positions."
        )
        return {}
    except OSError as exc:
        logger.error(f"ENTRIES FILE UNREADABLE at {ENTRIES_FILE}: {exc}")
        return {}


def _save_entries(entries: dict):
    # Atomic write: serialize to a sibling .tmp file, then os.replace into
    # place. This guarantees that a SIGINT/OOM/container-kill mid-write
    # leaves either the old file intact or the new file complete — never
    # a truncated/half-JSON state that would silently zero out position
    # tracking on the next _load_entries.
    import os

    ENTRIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = ENTRIES_FILE.with_suffix(ENTRIES_FILE.suffix + ".tmp")
    tmp_path.write_text(json.dumps(entries, indent=2))
    os.replace(tmp_path, ENTRIES_FILE)


def _check_recent_fills(client):
    """Check if pending MLEG orders filled. Update ic_entries with actual credit."""
    from datetime import timedelta

    from alpaca.trading.enums import QueryOrderStatus
    from alpaca.trading.requests import GetOrdersRequest

    entries = _load_entries()
    updated = False

    try:
        orders = client.get_orders(
            filter=GetOrdersRequest(
                status=QueryOrderStatus.CLOSED,
                after=(datetime.now() - timedelta(days=2)).isoformat(),
                limit=20,
            )
        )
        for order in orders:
            if order.filled_avg_price and str(order.order_class) == "OrderClass.MLEG":
                fill_credit = abs(float(order.filled_avg_price))
                for key, entry in entries.items():
                    if entry.get("order_id") == str(order.id) and not entry.get("fill_confirmed"):
                        old = entry["credit"]
                        entry["credit"] = fill_credit
                        entry["fill_confirmed"] = True
                        updated = True
                        logger.info(
                            f"Fill confirmed {key}: est ${old:.2f} → actual ${fill_credit:.2f}"
                        )
    except Exception as e:
        logger.debug(f"Fill check: {e}")

    if updated:
        _save_entries(entries)


def _cancel_stale_orders(client):
    """Cancel open limit orders older than 2 hours. Stale orders block new entries."""
    from alpaca.trading.enums import QueryOrderStatus
    from alpaca.trading.requests import GetOrdersRequest

    try:
        orders = client.get_orders(filter=GetOrdersRequest(status=QueryOrderStatus.OPEN))
        for order in orders:
            if order.created_at:
                age_hours = (
                    datetime.now(order.created_at.tzinfo) - order.created_at
                ).total_seconds() / 3600
                if age_hours > 2:
                    client.cancel_order_by_id(order.id)
                    logger.info(f"Cancelled stale order {order.id} ({age_hours:.1f}h old)")
    except Exception as e:
        logger.warning(f"Stale order cleanup failed: {e}")


def _wait_for_fill(
    client, order_id: str, timeout_seconds: int = 120, poll_interval: int = 10
) -> tuple[bool, float | None]:
    """Poll order status until filled or timeout.

    Returns ``(filled, fill_price_abs)``. ``fill_price_abs`` is the absolute
    credit per share when the MLEG order fills, or ``None`` when unavailable.
    Downstream uses it to persist the *actual* entry credit instead of the
    pre-walk estimate, which makes profit-target and stop-loss thresholds
    correct.
    """
    import time

    elapsed = 0
    while elapsed < timeout_seconds:
        try:
            order = client.get_order_by_id(order_id)
            status = str(order.status)
            if "FILLED" in status.upper():
                raw_price = getattr(order, "filled_avg_price", None)
                fill_price = None
                if raw_price is not None:
                    try:
                        fill_price = abs(float(raw_price))
                    except (TypeError, ValueError):
                        fill_price = None
                logger.info(
                    f"Order {order_id} FILLED @ ${fill_price:.2f}"
                    if fill_price is not None
                    else f"Order {order_id} FILLED"
                )
                return True, fill_price
            if any(s in status.upper() for s in ["CANCELED", "CANCELLED", "EXPIRED", "REJECTED"]):
                logger.warning(f"Order {order_id} terminal status: {status}")
                return False, None
            logger.info(f"Order {order_id}: {status} ({elapsed}s/{timeout_seconds}s)")
        except Exception as e:
            logger.debug(f"Fill poll error: {e}")
        time.sleep(poll_interval)
        elapsed += poll_interval
    logger.warning(f"Order {order_id} not filled after {timeout_seconds}s")
    return False, None


def _count_open_ics(client) -> int:
    positions = client.get_all_positions()
    spy_options = [p for p in positions if p.symbol.startswith("SPY") and len(p.symbol) > 10]
    return len(spy_options) // 4


def _refresh_canonical_state() -> None:
    """Refresh canonical state files after an IC Simple run."""
    try:
        from scripts import sync_alpaca_state

        alpaca_data = sync_alpaca_state.sync_from_alpaca()
        sync_alpaca_state.update_system_state(alpaca_data)
        logger.info("Canonical state refreshed via sync_alpaca_state.py")
    except Exception as exc:
        logger.warning(f"Canonical state refresh failed: {exc}")

    try:
        from scripts import sync_closed_positions

        result = sync_closed_positions.sync_closed_positions(dry_run=False)
        logger.info(
            "Closed-trade ledger refresh: success=%s new_closed=%s total_closed=%s",
            result.get("success"),
            result.get("new_closed"),
            result.get("closed_total"),
        )
    except Exception as exc:
        logger.warning(f"Closed-trade ledger refresh failed: {exc}")

    try:
        from scripts.daily_verification import verify_today

        report = verify_today()
        logger.info(
            "Daily verification refreshed canonical metrics: equity=$%.2f daily_pnl=$%+.2f positions=%s",
            report.equity,
            report.daily_pnl,
            report.positions_count,
        )
    except Exception as exc:
        logger.warning(f"Daily verification refresh failed: {exc}")


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    import argparse

    parser = argparse.ArgumentParser(description="Simple IC system")
    parser.add_argument(
        "--mode", choices=["entry", "exit", "both", "status", "report", "learn"], default="both"
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info(f"IC SIMPLE | mode={args.mode} dry_run={args.dry_run}")
    logger.info("=" * 60)

    client = get_client()

    if args.mode in ("exit", "both"):
        logger.info("\n--- FILL CHECK ---")
        _check_recent_fills(client)

        logger.info("\n--- EXIT CHECK ---")
        if args.dry_run:
            logger.info("(dry run — would check exits)")
        else:
            check_exits(client)

    if args.mode in ("entry", "both"):
        logger.info("\n--- ENTRY CHECK ---")

        # FOMC blackout check (2 days before through 1 day after)
        fomc_str = _fomc_blackout_reason()
        fomc_blocked = fomc_str is not None
        if fomc_str is not None:
            logger.warning(f"FOMC blackout: {fomc_str}. No entry.")

        # ThumbGate pre-entry check: block patterns from past losses
        thumbgate_blocked = False
        try:
            gate_file = Path(__file__).parent.parent / "data" / "thumbgate_rules.json"
            if gate_file.exists():
                rules = json.loads(gate_file.read_text())
                for rule in rules:
                    if rule.get("active") and _thumbgate_matches(rule):
                        logger.warning(f"ThumbGate BLOCKED: {rule.get('reason', 'learned rule')}")
                        thumbgate_blocked = True
                        break
        except Exception as e:
            logger.debug(f"ThumbGate check skipped: {e}")

        # IV vs RV check: only sell premium when IV is rich (free data — no Alpaca SIP needed)
        iv_rv_blocked = False
        try:
            from src.data.free_greeks import get_iv_percentile, get_spy_iv, get_vix

            current_vix = get_vix()
            current_iv = get_spy_iv()
            iv_pctile = get_iv_percentile()

            if current_vix is not None:
                logger.info(f"VIX={current_vix}")
            if current_iv is not None and iv_pctile is not None:
                logger.info(f"SPY IV={current_iv:.1%} | IV Percentile={iv_pctile:.0f}%")
                # Block entry when IV percentile is very low (premium too cheap)
                if iv_pctile < 20:
                    logger.warning(
                        f"IV Percentile {iv_pctile:.0f}% < 20% — premium too cheap to sell"
                    )
                    iv_rv_blocked = True
                elif iv_pctile > 50:
                    logger.info(f"IV Percentile {iv_pctile:.0f}% — premium is rich, good to sell")
        except Exception as e:
            logger.debug(f"IV/RV check skipped: {e}")

        # REGIME GATE: Fail-closed. Unknown regime = no entry.
        regime_blocked = False
        try:
            from src.utils.regime_detector import RegimeDetector

            detector = RegimeDetector()
            snapshot = detector.detect_live_regime_with_prediction()
            logger.info(
                f"Regime: {snapshot.label} (id={snapshot.regime_id}, "
                f"confidence={snapshot.confidence:.2f}, VIX={snapshot.vix_level:.1f})"
            )
            if snapshot.regime_id < 0 or snapshot.confidence < 0.3:
                logger.warning(
                    f"REGIME BLOCKED: unknown/low-confidence regime "
                    f"(id={snapshot.regime_id}, conf={snapshot.confidence:.2f}). "
                    f"Fail-closed: no entry without regime clarity."
                )
                regime_blocked = True
            elif snapshot.regime_id >= 2:  # volatile or spike
                logger.warning(
                    f"REGIME BLOCKED: {snapshot.label} regime (id={snapshot.regime_id}). "
                    f"Iron condors require calm/low-trend markets."
                )
                regime_blocked = True
            elif hasattr(snapshot, "transition_prediction") and snapshot.transition_prediction:
                tp = snapshot.transition_prediction
                if tp.transition_detected and tp.predicted_regime in ("volatile", "spike"):
                    logger.warning(
                        f"REGIME WARNING: Transition to {tp.predicted_regime} predicted "
                        f"(prob={tp.transition_probability:.2f}). Blocking entry."
                    )
                    regime_blocked = True
        except Exception as e:
            logger.warning(f"REGIME BLOCKED: detection failed ({e}). Fail-closed.")
            regime_blocked = True

        # SAME-EXPIRY RE-ENTRY BLOCK: no re-entry on an expiry that already lost
        losing_expiries = _load_losing_expiries()
        if losing_expiries:
            logger.info(f"Losing expiries (re-entry blocked): {losing_expiries}")

        # BROKER SYNC FRESHNESS GATE: no entry if sync is stale (>2h)
        sync_blocked = False
        try:
            ss = json.loads(
                (Path(__file__).parent.parent / "data" / "system_state.json").read_text()
            )
            last_sync = ss.get("sync_health", {}).get("last_successful_sync", "")
            if last_sync:
                sync_dt = datetime.fromisoformat(last_sync.replace("+00:00", ""))
                sync_age_hours = (datetime.utcnow() - sync_dt).total_seconds() / 3600
                if sync_age_hours > 2:
                    logger.warning(
                        f"SYNC STALE: last sync {sync_age_hours:.1f}h ago. "
                        f"No entry without fresh broker data."
                    )
                    sync_blocked = True
                else:
                    logger.info(f"Broker sync fresh: {sync_age_hours:.1f}h ago")
        except Exception as e:
            logger.debug(f"Sync freshness check skipped: {e}")

        # Cancel stale unfilled orders before checking entry
        _cancel_stale_orders(client)

        # Position limit
        ic_count = _count_open_ics(client)
        if fomc_blocked or thumbgate_blocked or iv_rv_blocked or regime_blocked or sync_blocked:
            pass  # Skip entry
        elif ic_count >= MAX_IC:
            logger.info(f"Position limit: {ic_count}/{MAX_IC} ICs. No new entry.")
        else:
            spy_price = get_spy_price(client)
            logger.info(f"SPY: ${spy_price:.2f}")

            # Pre-trade research via Perplexity (advisory, non-blocking)
            try:
                from src.research.pre_trade_research import get_pre_trade_research

                vix_val = current_vix if "current_vix" in dir() and current_vix else 0
                regime_label = snapshot.label if "snapshot" in dir() else "unknown"
                research = get_pre_trade_research(
                    spy_price=spy_price, vix=vix_val, regime=regime_label
                )
                if research.get("summary"):
                    logger.info(f"Perplexity: {research['summary'][:120]}")
            except Exception as e:
                logger.debug(f"Pre-trade research skipped: {e}")

            # Thompson Sampling confidence check
            thompson_conf = _get_thompson_confidence()
            logger.info(f"Thompson confidence: {thompson_conf:.3f}")

            # RAG: retrieve relevant lessons for current conditions
            _query_rag_before_entry(spy_price)

            # Place ONE IC per run — safe, predictable, no runaway loops.
            # Cross-process serialization (LL-281): the position-count read
            # and the broker submission below run as a critical section so
            # workflow_dispatch racing the 11am ET cron cannot produce two
            # simultaneous entries that both see ic_count < MAX_IC.
            from src.safety.trade_lock import TradeLockTimeout, acquire_trade_lock

            try:
                with acquire_trade_lock(timeout=10):
                    ic_count = _count_open_ics(client)
                    if ic_count >= MAX_IC:
                        logger.info(f"Position limit: {ic_count}/{MAX_IC} ICs. No new entry.")
                    else:
                        opp = find_opportunity(spy_price)
                        if opp:
                            # Daily entry limit ("1 IC per day"). Cron fires
                            # once at 11am ET but workflow_dispatch can re-
                            # trigger within the same day; without this
                            # guard, only MAX_IC=2 concurrent caps it.
                            try:
                                from src.core.trading_constants import MAX_DAILY_STRUCTURES
                            except ImportError:
                                MAX_DAILY_STRUCTURES = 1
                            today_iso = datetime.now().date().isoformat()
                            structures_today = 0
                            if SYSTEM_STATE_FILE.exists():
                                try:
                                    state = json.loads(
                                        SYSTEM_STATE_FILE.read_text(encoding="utf-8")
                                    )
                                    history = state.get("trade_history", []) or []
                                    structures_today = sum(
                                        1
                                        for row in history
                                        if isinstance(row, dict)
                                        and row.get("strategy") == "iron_condor"
                                        and str(row.get("entry_date", "")).startswith(
                                            today_iso
                                        )
                                    )
                                except (OSError, ValueError):
                                    structures_today = 0
                            if structures_today >= MAX_DAILY_STRUCTURES:
                                logger.warning(
                                    f"DAILY ENTRY LIMIT: already opened {structures_today} "
                                    f"iron condor(s) today (max {MAX_DAILY_STRUCTURES}). Skip."
                                )
                                opp = None
                        if opp and opp.get("expiry", "") in losing_expiries:
                            logger.warning(
                                f"RE-ENTRY BLOCKED: expiry {opp['expiry']} already had a losing trade. "
                                f"No same-expiry re-entry after loss."
                            )
                            opp = None
                        if opp:
                            from src.risk.expiry_concentration import (
                                check_recent_expiry_concentration,
                            )

                            blocked, ts_reason = check_recent_expiry_concentration(
                                opp["expiry"]
                            )
                            if blocked:
                                logger.warning(
                                    f"RE-ENTRY BLOCKED by time-series concentration: {ts_reason}"
                                )
                                opp = None
                        if opp:
                            should_skip, thompson_reason = _should_skip_for_thompson(
                                thompson_conf
                            )
                            if should_skip:
                                logger.warning(thompson_reason)
                            else:
                                if thompson_conf < THOMPSON_MIN_CONFIDENCE:
                                    logger.info(thompson_reason)
                                if args.dry_run:
                                    logger.info(f"(dry run — would place IC: {opp})")
                                else:
                                    order_id = place_ic(client, opp)
                                    logger.info(f"Placed IC: order={order_id}")
                        else:
                            logger.info("No opportunity found.")
            except TradeLockTimeout as lock_err:
                logger.warning(
                    f"Trade lock unavailable ({lock_err}). Another ic_simple.py "
                    "run is in the entry critical section — skipping this tick."
                )

    if args.mode == "status":
        ic_count = _count_open_ics(client)
        account = client.get_account()
        logger.info(f"Equity: ${float(account.equity):,.2f}")
        logger.info(f"Open ICs: {ic_count}/{MAX_IC}")
        logger.info(f"Today P/L: ${float(account.equity) - float(account.last_equity):+,.2f}")

    if args.mode in ("entry", "exit", "both", "status") and not args.dry_run:
        logger.info("\n--- CANONICAL STATE REFRESH ---")
        _refresh_canonical_state()

    if args.mode == "report":
        _print_report()

    if args.mode == "learn":
        _weekend_learn()

    # Continuous learning: run research + report on every execution (not just weekends)
    if args.mode in ("both", "exit") and not args.dry_run:
        _daily_learn()

    logger.info("\nDone.")


if __name__ == "__main__":
    main()
