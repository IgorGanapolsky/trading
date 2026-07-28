#!/usr/bin/env python3
"""Mercury -> Broker -> Mercury Autonomous Income Loop (dividend_growth_income).

Automates funds flow between Mercury bank and equity brokerage with after-tax profit target
accounting ($1,000/month default after-tax target).

Key Design Principles:
1. Tax Efficiency (Buy-and-Hold Qualified Dividend Strategy vs Day Trading):
   - Day trading generates short-term capital gains taxed as ordinary income (up to 37% + state).
   - Day trading triggers Wash Sale rules (IRC § 1091) if losses occur within 30 days.
   - Buy-and-Hold Dollar-Cost-Averaging (DCA) into qualified dividend growth ETFs (e.g. SCHD, VIG, DGRO)
     yields qualified dividends taxed at long-term rates (0%, 15%, 20%).
2. Tax Reservation Accounting:
   - Configured via --tax-rate-pct (default: 20.0%, covering 15% federal + 5% state tax reserve).
   - For every dollar of gross dividend/realized profit:
     - tax_amount = gross * (tax_rate_pct / 100.0)
     - after_tax = gross - tax_amount
   - Once accumulated after-tax profit reaches --profit-return-threshold-usd ($1,000.00 default),
     the net after-tax funds are deposited back to Mercury bank, while tax reserves remain tracked.
3. Execution Modes:
   - Paper Mode (--mode paper, default): Safe in-memory simulation using PaperBankAdapter and
     PaperEquityBrokerAdapter. Persists state & positions to data/mercury_income_loop_state.json.
   - Live Mode (--mode live): Uses MercuryBankAdapter and AlpacaEquityBrokerAdapter if real
     credentials (MERCURY_API_TOKEN, MERCURY_ACCOUNT_ID, MERCURY_LIVE_TRANSFERS_ENABLED=1,
     DIVIDEND_GROWTH_ALPACA_API_KEY, DIVIDEND_GROWTH_ALPACA_API_SECRET,
     DIVIDEND_GROWTH_ALPACA_ENABLED=1) are present in the environment.

Each scheduled run executes one cycle:
  1. Check Mercury bank balance; push surplus above buffer to broker.
  2. Execute DCA purchases using DividendGrowthStrategy.
  3. Collect dividend income and calculate tax reserve vs net after-tax profit.
  4. Deposit net after-tax proceeds back to Mercury bank once threshold is crossed.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.adapters.bank_adapter import BankAdapter, MercuryBankAdapter, PaperBankAdapter  # noqa: E402
from src.adapters.equity_broker_adapter import (  # noqa: E402
    AlpacaEquityBrokerAdapter,
    EquityBrokerAdapter,
    PaperEquityBrokerAdapter,
)
from src.bank.subaccounts import MercurySubAccountManager  # noqa: E402
from src.strategies.dividend_growth_strategy import DividendGrowthStrategy  # noqa: E402

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE_PATH = ROOT / "data" / "mercury_income_loop_state.json"

DEFAULT_BANK_BUFFER_USD = 500.0  # leave this buffer untouched in Mercury bank
DEFAULT_PROFIT_RETURN_THRESHOLD_USD = 1000.0  # deposit proceeds back to Mercury once $1,000 net after-tax accrues
DEFAULT_TAX_RATE_PCT = 20.0  # estimated qualified tax reserve rate (15% federal + 5% state buffer)


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "principal_deployed_usd": 0.0,
            "gross_profit_usd": 0.0,
            "realized_profit_usd": 0.0,
            "realized_after_tax_profit_usd": 0.0,
            "tax_reserve_usd": 0.0,
            "total_deposited_to_bank_usd": 0.0,
            "positions": {},
            "events": [],
        }
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
        data.setdefault("principal_deployed_usd", 0.0)
        data.setdefault("gross_profit_usd", 0.0)
        data.setdefault("realized_profit_usd", 0.0)
        data.setdefault("realized_after_tax_profit_usd", data.get("realized_profit_usd", 0.0))
        data.setdefault("tax_reserve_usd", 0.0)
        data.setdefault("total_deposited_to_bank_usd", 0.0)
        data.setdefault("positions", {})
        data.setdefault("events", [])
        return data


def _save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, sort_keys=True)


def run_once(
    bank: BankAdapter,
    strategy: DividendGrowthStrategy,
    state: dict[str, Any],
    *,
    equity_broker: EquityBrokerAdapter,
    bank_buffer_usd: float = DEFAULT_BANK_BUFFER_USD,
    profit_return_threshold_usd: float = DEFAULT_PROFIT_RETURN_THRESHOLD_USD,
    tax_rate_pct: float = DEFAULT_TAX_RATE_PCT,
) -> dict[str, Any]:
    """Run a single cycle of the Mercury autonomous income loop."""

    now = datetime.now(timezone.utc).isoformat()
    balance = bank.get_balance()
    surplus = balance.available_usd - bank_buffer_usd

    # 1. Withdraw bank surplus to broker for DCA buy
    if surplus > 0:
        transfer = bank.send_to_broker(surplus, idempotency_key=str(uuid.uuid4()))
        state["events"].append({"type": "withdraw", "at": now, **asdict(transfer)})
        if transfer.success:
            state["principal_deployed_usd"] += surplus
            for order in strategy.plan_purchase(surplus):
                buy_result = equity_broker.buy(order.symbol, order.notional_usd)
                state["events"].append({"type": "dca_buy", "at": now, **asdict(buy_result)})
    else:
        logger.info("No surplus above the $%.2f buffer; nothing to withdraw", bank_buffer_usd)

    # 2. Collect dividend income & apply tax reservation
    dividend_income = equity_broker.collect_dividend_income()
    if dividend_income.total_usd > 0:
        gross = dividend_income.total_usd
        tax_amount = gross * (tax_rate_pct / 100.0)
        after_tax_amount = gross - tax_amount

        state["gross_profit_usd"] += gross
        state["tax_reserve_usd"] += tax_amount
        state["realized_after_tax_profit_usd"] += after_tax_amount
        state["realized_profit_usd"] = state["realized_after_tax_profit_usd"]

        state["events"].append(
            {
                "type": "dividend_income_collected",
                "at": now,
                "gross_amount_usd": gross,
                "tax_reserve_usd": tax_amount,
                "after_tax_amount_usd": after_tax_amount,
                "tax_rate_pct": tax_rate_pct,
            }
        )

    # 3. If accumulated after-tax profit crosses the deposit threshold, send proceeds back to bank
    if state["realized_after_tax_profit_usd"] >= profit_return_threshold_usd:
        payout = state["realized_after_tax_profit_usd"]
        transfer = bank.record_incoming_from_broker(payout)
        state["events"].append({"type": "deposit", "at": now, **asdict(transfer)})
        if transfer.success:
            state["total_deposited_to_bank_usd"] += payout
            # Automate Mercury sub-account allocation split
            sub_mgr = MercurySubAccountManager()
            sub_split = sub_mgr.calculate_auto_transfer_split(payout, tax_pct=tax_rate_pct, profit_pct=10.0)
            state["events"].append({"type": "subaccount_split", "at": now, **sub_split.as_dict()})
            state["realized_after_tax_profit_usd"] = 0.0
            state["realized_profit_usd"] = 0.0

    # 4. Save position state if broker supports it
    if hasattr(equity_broker, "get_positions"):
        state["positions"] = equity_broker.get_positions()

    return state


def parse_args(args_list: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=["paper", "live"],
        default="paper",
        help="Execution mode: paper (default simulated) or live (real Mercury & Alpaca accounts)",
    )
    parser.add_argument("--state-path", type=Path, default=DEFAULT_STATE_PATH)
    parser.add_argument("--paper-starting-balance", type=float, default=1500.0)
    parser.add_argument("--bank-buffer-usd", type=float, default=DEFAULT_BANK_BUFFER_USD)
    parser.add_argument(
        "--profit-return-threshold-usd",
        type=float,
        default=DEFAULT_PROFIT_RETURN_THRESHOLD_USD,
        help="After-tax profit return threshold to deposit back to bank (default: $1000.00)",
    )
    parser.add_argument(
        "--tax-rate-pct",
        "--tax-rate",
        dest="tax_rate_pct",
        type=float,
        default=DEFAULT_TAX_RATE_PCT,
        help="Estimated tax reserve percentage (default: 20.0%%)",
    )
    parser.add_argument(
        "--recipient-id",
        type=str,
        default=os.environ.get("MERCURY_RECIPIENT_ID", "brokerage-recipient-id"),
        help="Mercury recipient ID for broker transfers",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Alias for --mode live (used by run_autonomous_trading.py)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print final state as JSON (always on; flag kept for scheduler compatibility)",
    )
    parser.add_argument(
        "--ledger-path",
        type=Path,
        default=None,
        help="Optional JSONL ledger; one line appended per completed cycle",
    )
    args = parser.parse_args(args_list)
    if args.live:
        args.mode = "live"
    return args


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    args = parse_args()

    state = _load_state(args.state_path)
    events_before = len(state.get("events", []))

    if args.mode == "live":
        logger.info("Initializing LIVE Mercury Bank and Alpaca Broker Adapters...")
        bank = MercuryBankAdapter.from_env(recipient_id=args.recipient_id)
        equity_broker = AlpacaEquityBrokerAdapter.from_env()
    else:
        logger.info("Initializing PAPER Bank and Equity Broker Adapters...")
        bank = PaperBankAdapter(starting_balance_usd=args.paper_starting_balance)
        equity_broker = PaperEquityBrokerAdapter(
            initial_positions=state.get("positions", {})
        )

    strategy = DividendGrowthStrategy()

    state = run_once(
        bank,
        strategy,
        state,
        equity_broker=equity_broker,
        bank_buffer_usd=args.bank_buffer_usd,
        profit_return_threshold_usd=args.profit_return_threshold_usd,
        tax_rate_pct=args.tax_rate_pct,
    )

    _save_state(args.state_path, state)

    if args.ledger_path:
        args.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        direction_names = {"to_broker": "mercury_to_broker", "to_bank": "broker_to_mercury"}
        with args.ledger_path.open("a", encoding="utf-8") as handle:
            for event in state.get("events", [])[events_before:]:
                if event.get("type") not in ("withdraw", "deposit") or not event.get("success"):
                    continue
                handle.write(
                    json.dumps(
                        {
                            "ts": event.get("at") or event.get("initiated_at"),
                            "direction": direction_names.get(
                                event.get("direction"), event.get("direction")
                            ),
                            "amount_usd": event.get("amount_usd"),
                            "transfer_id": event.get("transfer_id"),
                            "mode": args.mode,
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )

    print(json.dumps(state, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
