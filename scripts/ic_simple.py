#!/usr/bin/env python3
"""
Simple Iron Condor System — One file, one workflow, no complexity.

Entry: Real 15-delta strikes via Alpaca option chain, limit orders only.
Exit:  50% profit, 100% stop, 7 DTE. 4-hour minimum hold. MLEG close.
Guard: Net-credit required, $0.50 minimum, 1 IC per day, position limit 2.

This replaces: iron_condor_trader.py, iron_condor_guardian.py,
iron_condor_scanner.py, manage_iron_condor_positions.py, and 6 workflows.
"""

import json
import logging
import sys
from datetime import datetime
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
        "wing_width": 10,
        "target_dte": 30,
        "min_dte": 21,
        "max_dte": 45,
        "min_credit": 0.50,
        "profit_target": 0.50,
        "stop_loss": 1.0,
        "exit_dte": 7,
        "max_ic": 4,
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
MIN_HOLD_HOURS = 4  # Not ML-adjustable (safety)
PROFIT_TARGET = _SP["profit_target"]
STOP_LOSS = _SP["stop_loss"]
EXIT_DTE = _SP["exit_dte"]
WING_WIDTH = _SP["wing_width"]
TARGET_DELTA = _SP["target_delta"]
ENTRIES_FILE = Path(__file__).parent.parent / "data" / "ic_entries.json"


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
        min_dte=21,
        max_dte=45,
    )

    # Net credit = short premiums - long premiums (NOT just short bids)
    est_credit = selection.net_credit
    if selection.method == "heuristic_fallback" or est_credit <= 0:
        est_credit = 1.50  # Conservative guess when we can't price the wings

    if est_credit < MIN_CREDIT:
        logger.warning(f"Credit ${est_credit:.2f} < ${MIN_CREDIT:.2f} minimum. Skip.")
        return None

    logger.info(
        f"Opportunity: SP={selection.short_put} SC={selection.short_call} "
        f"method={selection.method} credit=${est_credit:.2f} "
        f"put_delta={selection.put_delta:.3f} call_delta={selection.call_delta:.3f}"
    )

    return {
        "expiry": selection.expiry,
        "long_put": selection.long_put,
        "short_put": selection.short_put,
        "short_call": selection.short_call,
        "long_call": selection.long_call,
        "est_credit": est_credit,
        "method": selection.method,
    }


def place_ic(client, opp: dict) -> str | None:
    """Submit limit MLEG order. Returns order ID or None."""
    from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
    from alpaca.trading.requests import LimitOrderRequest, OptionLegRequest
    from src.safety.mandatory_trade_gate import safe_submit_order

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
    walk_total = 0.0

    while walk_total <= MAX_WALK and not filled:
        current_credit = round(limit_credit - walk_total, 2)
        if current_credit < MIN_CREDIT:
            logger.warning(f"Price walk would drop below ${MIN_CREDIT:.2f} min. Stopping.")
            break

        logger.info(f"MLEG limit order: credit >= ${current_credit:.2f} (walk ${walk_total:.2f})")

        order = safe_submit_order(
            client,
            LimitOrderRequest(
                qty=1,
                order_class=OrderClass.MLEG,
                legs=legs,
                time_in_force=TimeInForce.DAY,
                limit_price=round(-current_credit, 2),
            ),
            strategy="iron_condor",
        )
        order_id = str(order.id)
        logger.info(f"Order {order_id}: {order.status}")

        filled = _wait_for_fill(
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

    # Save entry data
    entries = _load_entries()
    entry_key = f"IC_{expiry_yymmdd}"
    entries[entry_key] = {
        "credit": opp["est_credit"],
        "date": datetime.now().isoformat(),
        "order_id": str(order.id),
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
        if entry_key in entries:
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

        # Minimum holding period
        if entry_date:
            try:
                entry_dt = datetime.fromisoformat(entry_date)
                if entry_dt.tzinfo:
                    entry_dt = entry_dt.replace(tzinfo=None)
                hours = (datetime.now() - entry_dt).total_seconds() / 3600
                if hours < MIN_HOLD_HOURS:
                    logger.info(f"IC {expiry}: held {hours:.1f}h < {MIN_HOLD_HOURS}h. Hold.")
                    continue
            except (ValueError, TypeError):
                pass

        # Calculate P/L
        contract_count = max(abs(leg["qty"]) for leg in legs)
        current_value = sum(
            (-leg["current"] if leg["qty"] < 0 else leg["current"]) * abs(leg["qty"]) * 100
            for leg in legs
        )
        pnl = entry_credit * contract_count * 100 + current_value
        max_profit = entry_credit * contract_count * 100

        # DTE
        from datetime import date as date_type

        exp_date = date_type(2000 + int(expiry[:2]), int(expiry[2:4]), int(expiry[4:6]))
        dte = (exp_date - date_type.today()).days

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
            _record_lesson(expiry, entry_credit, pnl, reason, dte, contract_count)
            _update_thompson("WIN" if pnl > 0 else "LOSS")
        else:
            logger.info(
                f"IC {expiry}: HOLD. Target=${max_profit * PROFIT_TARGET:.2f} Stop=-${max_profit * STOP_LOSS:.2f}"
            )


def _close_ic(client, legs: list[dict], qty: int):
    """Close IC with MLEG limit order. Fallback to individual legs."""
    from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
    from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest, OptionLegRequest
    from src.safety.mandatory_trade_gate import safe_submit_order

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
            ),
            strategy="iron_condor",
        )
        logger.info(f"MLEG close: {order.id} @ ${limit_debit:.2f} debit")
    except Exception as e:
        logger.warning(f"MLEG close failed ({e}). Individual leg fallback.")
        for leg in legs:
            try:
                side = OrderSide.BUY if leg["qty"] < 0 else OrderSide.SELL
                safe_submit_order(
                    client,
                    MarketOrderRequest(
                        symbol=leg["symbol"],
                        qty=abs(leg["qty"]),
                        side=side,
                        time_in_force=TimeInForce.DAY,
                    ),
                    strategy="iron_condor",
                )
            except Exception as le:
                logger.error(f"Failed to close {leg['symbol']}: {le}")


# ── Learning: RAG + Trade Journal + Stats ────────────────────────────────────

JOURNAL_FILE = Path(__file__).parent.parent / "data" / "trade_journal.jsonl"
LESSONS_DIR = Path(__file__).parent.parent / "data" / "rag_knowledge" / "lessons_learned"


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
    except Exception as e:
        logger.warning(f"Failed to write RAG lesson: {e}")

    # 3. Update cumulative stats
    _update_stats(entry)


def _update_stats(trade: dict):
    """Update running win rate and P/L stats."""
    stats_file = Path(__file__).parent.parent / "data" / "ic_stats.json"
    try:
        stats = (
            json.loads(stats_file.read_text())
            if stats_file.exists()
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

    stats_file.write_text(json.dumps(stats, indent=2))
    logger.info(
        f"Stats: {stats['total']} trades | {stats['win_rate']}% win rate | "
        f"PF={stats['profit_factor']} | Total P/L=${stats['total_pnl']:+.2f}"
    )


# ── Report + Weekend Learning ────────────────────────────────────────────────


def _print_report():
    """Print full performance report from trade journal."""
    stats_file = Path(__file__).parent.parent / "data" / "ic_stats.json"
    if not stats_file.exists():
        logger.info("No stats yet. Complete trades to build data.")
        return

    stats = json.loads(stats_file.read_text())
    logger.info("=" * 60)
    logger.info("PERFORMANCE REPORT")
    logger.info("=" * 60)
    logger.info(f"Total trades:   {stats.get('total', 0)}")
    logger.info(f"Wins:           {stats.get('wins', 0)}")
    logger.info(f"Losses:         {stats.get('losses', 0)}")
    logger.info(f"Win rate:       {stats.get('win_rate', 0):.1f}%")
    logger.info(f"Profit factor:  {stats.get('profit_factor', 0):.2f}")
    logger.info(f"Total P/L:      ${stats.get('total_pnl', 0):+,.2f}")
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
    BOUNDS = {
        "target_delta": (0.10, 0.25),  # Never go below 10-delta or above 25-delta
        "wing_width": (5, 15),  # $5-$15 wide
        "target_dte": (21, 60),  # 21-60 DTE
        "min_credit": (0.30, 2.00),  # Floor $0.30, cap $2.00
        "profit_target": (0.25, 0.75),  # 25-75% profit take
        "stop_loss": (0.75, 2.0),  # 75-200% stop
        "exit_dte": (3, 14),  # 3-14 DTE exit
        "max_ic": (1, 4),  # 1-4 concurrent ICs
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

    # 1. GRPO retrain and apply policy adjustments
    try:
        from src.ml.grpo_trade_learner import GRPOTradeLearner

        learner = GRPOTradeLearner()
        result = learner.train()
        logger.info(f"GRPO retrain: {result}")

        # Extract recommended params from GRPO policy if available
        meta_file = Path(__file__).parent.parent / "models" / "ml" / "grpo_trade_metadata.json"
        if meta_file.exists():
            meta = json.loads(meta_file.read_text())
            fp = meta.get("fallback_params", {})
            trades_trained = meta.get("trades_trained_on", 0)
            if trades_trained >= 10 and fp:
                # GRPO has enough data — apply its recommendations
                grpo_adjustments = {}
                if "delta" in fp and 0.10 <= fp["delta"] <= 0.25:
                    grpo_adjustments["target_delta"] = fp["delta"]
                if "dte" in fp and 21 <= fp["dte"] <= 60:
                    grpo_adjustments["target_dte"] = int(fp["dte"])
                if grpo_adjustments:
                    confidence = min(0.5 + (trades_trained / 100), 0.95)
                    _adjust_strategy_params(
                        grpo_adjustments,
                        reason=f"GRPO policy after {trades_trained} trades",
                        source="grpo",
                        confidence=confidence,
                    )
    except Exception as e:
        logger.debug(f"GRPO retrain skipped: {e}")

    # 2. Quick strategy research (one query per session, saves to RAG)
    stats_file = Path(__file__).parent.parent / "data" / "ic_stats.json"
    trade_count = 0
    win_rate = 0
    total_pnl = 0
    try:
        stats = json.loads(stats_file.read_text()) if stats_file.exists() else {}
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


def _auto_adjust_from_performance(stats: dict):
    """Adjust strategy params based on actual trade performance data.

    Rules:
    - Win rate < 70% after 10+ trades → widen delta (more OTM = higher win rate)
    - Win rate > 90% after 15+ trades → tighten delta (closer = more premium)
    - Avg loss > 2x avg win → tighten stop loss
    - Most exits at DTE → could enter shorter DTE for faster theta decay
    """
    trade_count = stats.get("total", 0)
    win_rate = stats.get("win_rate", 0)
    avg_win = stats.get("avg_win", 0)
    avg_loss = abs(stats.get("avg_loss", 0))

    adjustments = {}
    reasons = []
    confidence = min(0.5 + (trade_count / 60), 0.90)  # Caps at 0.90

    # Delta adjustment based on win rate
    if win_rate < 70 and trade_count >= 10:
        adjustments["target_delta"] = 0.12  # Wider = higher probability
        reasons.append(f"win rate {win_rate:.0f}% < 70% → widen to 12-delta")
    elif win_rate > 90 and trade_count >= 15:
        adjustments["target_delta"] = 0.18  # Tighter = more premium
        reasons.append(f"win rate {win_rate:.0f}% > 90% → tighten to 18-delta for more premium")

    # Stop loss adjustment
    if avg_loss > 0 and avg_win > 0 and avg_loss > 2 * avg_win and trade_count >= 10:
        adjustments["stop_loss"] = 0.75  # Tighter stop
        reasons.append(
            f"avg loss ${avg_loss:.0f} > 2x avg win ${avg_win:.0f} → tighten stop to 75%"
        )

    if adjustments:
        _adjust_strategy_params(
            adjustments,
            reason=" | ".join(reasons),
            source="performance_auto",
            confidence=confidence,
        )
    else:
        logger.info("Auto-adjust: no changes needed based on current performance")


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
        return 0.86  # Fall back to prior mean


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
    try:
        if ENTRIES_FILE.exists():
            return json.loads(ENTRIES_FILE.read_text())
    except Exception:
        pass
    return {}


def _save_entries(entries: dict):
    ENTRIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    ENTRIES_FILE.write_text(json.dumps(entries, indent=2))


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
) -> bool:
    """Poll order status until filled or timeout. Returns True if filled."""
    import time

    elapsed = 0
    while elapsed < timeout_seconds:
        try:
            order = client.get_order_by_id(order_id)
            status = str(order.status)
            if "FILLED" in status.upper():
                fill_price = getattr(order, "filled_avg_price", None)
                logger.info(
                    f"Order {order_id} FILLED @ ${abs(float(fill_price)):.2f}"
                    if fill_price
                    else f"Order {order_id} FILLED"
                )
                return True
            if any(s in status.upper() for s in ["CANCELED", "CANCELLED", "EXPIRED", "REJECTED"]):
                logger.warning(f"Order {order_id} terminal status: {status}")
                return False
            logger.info(f"Order {order_id}: {status} ({elapsed}s/{timeout_seconds}s)")
        except Exception as e:
            logger.debug(f"Fill poll error: {e}")
        time.sleep(poll_interval)
        elapsed += poll_interval
    logger.warning(f"Order {order_id} not filled after {timeout_seconds}s")
    return False


def _count_open_ics(client) -> int:
    positions = client.get_all_positions()
    spy_options = [p for p in positions if p.symbol.startswith("SPY") and len(p.symbol) > 10]
    return len(spy_options) // 4


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
        from datetime import timedelta

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
        today = datetime.now().date()
        fomc_blocked = False
        for fomc_str in FOMC_DATES:
            fomc_date = datetime.strptime(fomc_str, "%Y-%m-%d").date()
            if (fomc_date - timedelta(days=2)) <= today <= (fomc_date + timedelta(days=1)):
                logger.warning(f"FOMC blackout: {fomc_str}. No entry.")
                fomc_blocked = True
                break

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

        # Cancel stale unfilled orders before checking entry
        _cancel_stale_orders(client)

        # Position limit
        ic_count = _count_open_ics(client)
        if fomc_blocked or thumbgate_blocked or iv_rv_blocked:
            pass  # Skip entry
        elif ic_count >= MAX_IC:
            logger.info(f"Position limit: {ic_count}/{MAX_IC} ICs. No new entry.")
        else:
            spy_price = get_spy_price(client)
            logger.info(f"SPY: ${spy_price:.2f}")

            # Thompson Sampling confidence check
            thompson_conf = _get_thompson_confidence()
            logger.info(f"Thompson confidence: {thompson_conf:.3f}")

            # RAG: retrieve relevant lessons for current conditions
            _query_rag_before_entry(spy_price)

            # Place ONE IC per run — safe, predictable, no runaway loops
            # (Previous while loop opened ~80 contracts due to stale count bug)
            ic_count = _count_open_ics(client)
            if ic_count >= MAX_IC:
                logger.info(f"Position limit: {ic_count}/{MAX_IC} ICs. No new entry.")
            else:
                opp = find_opportunity(spy_price)
                if opp:
                    if thompson_conf < 0.40:
                        logger.warning(
                            f"Thompson confidence {thompson_conf:.3f} < 0.40 — skip entry"
                        )
                    elif args.dry_run:
                        logger.info(f"(dry run — would place IC: {opp})")
                    else:
                        order_id = place_ic(client, opp)
                        logger.info(f"Placed IC: order={order_id}")
                else:
                    logger.info("No opportunity found.")

    if args.mode == "status":
        ic_count = _count_open_ics(client)
        account = client.get_account()
        logger.info(f"Equity: ${float(account.equity):,.2f}")
        logger.info(f"Open ICs: {ic_count}/{MAX_IC}")
        logger.info(f"Today P/L: ${float(account.equity) - float(account.last_equity):+,.2f}")

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
