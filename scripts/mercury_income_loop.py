#!/usr/bin/env python3
"""Mercury -> broker -> Mercury income loop orchestrator (dividend_growth_income).

Paper mode is the only mode this script can reach today: PaperBankAdapter never
makes a network call, and AlpacaTrader defaults to paper=True. Wiring in
MercuryBankAdapter and a live Alpaca account requires explicit env vars that
this script never sets on its own (see src/adapters/bank_adapter.py) - that is
a deliberate stop, not an oversight, until real capital and explicit sign-off
exist. See config/strategy_candidate_tournament.json's dividend_growth_income
entry and .claude/rules/controlled-experiment.md for why nothing here claims
edge or opens real risk yet.

Each run is one step of the loop, meant to be invoked on a schedule:
  1. Check bank balance; if above the configured buffer, push the surplus to
     the broker.
  2. Once broker cash has settled, buy the DCA allocation via
     DividendGrowthStrategy.
  3. If accumulated broker cash (i.e. dividends/proceeds, tracked separately
     from principal so the "only cycle realized profit" rule holds) exceeds
     the configured threshold, push it back to the bank.

State persists to data/mercury_income_loop_state.json, the same
one-journal-file-per-workflow convention as data/put_credit_entries.json.
"""

from __future__ import annotations

import argparse
import json
import logging
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.adapters.bank_adapter import BankAdapter, PaperBankAdapter
from src.strategies.dividend_growth_strategy import DividendGrowthStrategy

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE_PATH = ROOT / "data" / "mercury_income_loop_state.json"

DEFAULT_BANK_BUFFER_USD = 500.0  # leave this much at the bank untouched
DEFAULT_PROFIT_RETURN_THRESHOLD_USD = 50.0  # send proceeds back once this much accrues


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"principal_deployed_usd": 0.0, "realized_profit_usd": 0.0, "events": []}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, sort_keys=True)


def run_once(
    bank: BankAdapter,
    strategy: DividendGrowthStrategy,
    state: dict[str, Any],
    *,
    bank_buffer_usd: float = DEFAULT_BANK_BUFFER_USD,
    profit_return_threshold_usd: float = DEFAULT_PROFIT_RETURN_THRESHOLD_USD,
) -> dict[str, Any]:
    """Run a single step. Mutates and returns the state dict; caller persists it."""

    now = datetime.now(timezone.utc).isoformat()
    balance = bank.get_balance()
    surplus = balance.available_usd - bank_buffer_usd

    if surplus > 0:
        transfer = bank.send_to_broker(surplus, idempotency_key=str(uuid.uuid4()))
        state["events"].append({"type": "withdraw", "at": now, **asdict(transfer)})
        if transfer.success:
            state["principal_deployed_usd"] += surplus
            orders = strategy.plan_purchase(surplus)
            for order in orders:
                state["events"].append(
                    {
                        "type": "dca_buy_planned",
                        "at": now,
                        "symbol": order.symbol,
                        "notional_usd": order.notional_usd,
                    }
                )
    else:
        logger.info("No surplus above the $%.2f buffer; nothing to withdraw", bank_buffer_usd)

    if state["realized_profit_usd"] >= profit_return_threshold_usd:
        payout = state["realized_profit_usd"]
        transfer = bank.record_incoming_from_broker(payout)
        state["events"].append({"type": "deposit", "at": now, **asdict(transfer)})
        if transfer.success:
            state["realized_profit_usd"] = 0.0

    return state


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-path", type=Path, default=DEFAULT_STATE_PATH)
    parser.add_argument("--paper-starting-balance", type=float, default=0.0)
    parser.add_argument("--bank-buffer-usd", type=float, default=DEFAULT_BANK_BUFFER_USD)
    parser.add_argument(
        "--profit-return-threshold-usd", type=float, default=DEFAULT_PROFIT_RETURN_THRESHOLD_USD
    )
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    args = parse_args()

    # PaperBankAdapter only - MercuryBankAdapter is never constructed here.
    # Wiring in real credentials is a separate, explicit change, not a flag on
    # this script.
    bank = PaperBankAdapter(starting_balance_usd=args.paper_starting_balance)
    strategy = DividendGrowthStrategy()
    state = _load_state(args.state_path)

    state = run_once(
        bank,
        strategy,
        state,
        bank_buffer_usd=args.bank_buffer_usd,
        profit_return_threshold_usd=args.profit_return_threshold_usd,
    )

    _save_state(args.state_path, state)
    print(json.dumps(state, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
