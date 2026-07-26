#!/usr/bin/env python3
"""Mercury -> broker -> Mercury income loop orchestrator (dividend_growth_income).

Paper mode is the only mode this script can reach today: PaperBankAdapter and
PaperEquityBrokerAdapter never make network calls and never touch the
options-validation Alpaca account. Wiring in MercuryBankAdapter or
AlpacaEquityBrokerAdapter requires explicit, distinct env vars that this
script never sets on its own (see src/adapters/bank_adapter.py and
src/adapters/equity_broker_adapter.py) - that is a deliberate stop, not an
oversight, until real capital, a dedicated equity account, and explicit
sign-off all exist. See config/strategy_candidate_tournament.json's
dividend_growth_income entry and .claude/rules/controlled-experiment.md for
why nothing here claims edge or opens real risk yet.

Each run is one step of the loop, meant to be invoked on a schedule:
  1. Check bank balance; if above the configured buffer, push the surplus to
     the broker.
  2. Buy the DCA allocation via DividendGrowthStrategy, executed through
     EquityBrokerAdapter.
  3. Collect any accrued dividend income (tracked separately from principal
     so the "only cycle realized profit" rule holds).
  4. If accumulated realized profit exceeds the configured threshold, push it
     back to the bank.

State persists to data/mercury_income_loop_state.json, the same
one-journal-file-per-workflow convention as data/put_credit_entries.json.

Every transfer (withdraw or deposit) is also appended to the durable
transfer ledger (data/audit/mercury_broker_transfers.jsonl) via
src/bank/transfer_ledger.py, so remittance_status.py and
autonomous_money_cycle.py can compute after-tax progress toward the
$1000/mo bank-deposit target from ledger facts alone.

KNOWN LIMITATION: main() constructs a fresh PaperEquityBrokerAdapter on every
invocation, so simulated positions and dividend accrual do NOT persist across
scheduled runs the way the bank-side JSON state does - each run "forgets"
prior simulated buys. The withdraw/buy/collect/deposit wiring itself is
correct and unit-tested with a persistent broker instance across a single
run (tests/test_mercury_income_loop.py); this gap only matters if this script
were actually scheduled repeatedly, which it is not yet, and isn't worth
building real persistence for before there is real capital to deploy.
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
from src.adapters.equity_broker_adapter import EquityBrokerAdapter, PaperEquityBrokerAdapter
from src.bank.remittance import (
    MONTHLY_AFTER_TAX_TARGET_USD,
    compute_remittance_progress,
    estimate_after_tax_profit,
)
from src.bank.transfer_ledger import (
    TransferDirection,
    TransferStatus,
    append_transfer_record,
    build_transfer_record,
    load_transfer_ledger,
)
from src.strategies.dividend_growth_strategy import DividendGrowthStrategy

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE_PATH = ROOT / "data" / "mercury_income_loop_state.json"
DEFAULT_LEDGER_PATH = ROOT / "data" / "audit" / "mercury_broker_transfers.jsonl"

DEFAULT_BANK_BUFFER_USD = 500.0  # leave this much at the bank untouched
DEFAULT_PROFIT_RETURN_THRESHOLD_USD = 50.0  # send proceeds back once this much accrues

# Tax rates for after-tax profit estimation.
# SCHD pays qualified dividends (15% rate for most brackets) and long-term
# capital gains (15% rate). Short-term gains would be 37% but this strategy
# never realizes short-term gains by design (buy-and-hold > 1 year).
DEFAULT_QUALIFIED_DIVIDEND_TAX_RATE = 0.15
DEFAULT_LONG_TERM_CAPITAL_GAINS_TAX_RATE = 0.15


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "principal_deployed_usd": 0.0,
            "realized_profit_usd": 0.0,
            "realized_pre_tax_pnl_usd": 0.0,
            "events": [],
        }
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, sort_keys=True)


def _log_transfer(
    *,
    direction: TransferDirection,
    amount_usd: float,
    success: bool,
    dry_run: bool,
    reason: str,
    ledger_path: Path | None,
) -> None:
    """Append a transfer record to the durable ledger (best-effort, never raises)."""
    try:
        status = TransferStatus.CONFIRMED if success else TransferStatus.FAILED
        rec = build_transfer_record(
            direction=direction,
            amount_usd=amount_usd,
            status=status,
            dry_run=dry_run,
            reason=reason,
        )
        append_transfer_record(rec, ledger_path=ledger_path)
    except Exception as exc:  # noqa: BLE001 - ledger logging must never break the loop
        logger.warning("Failed to append transfer record to ledger: %s", exc)


def run_once(
    bank: BankAdapter,
    strategy: DividendGrowthStrategy,
    state: dict[str, Any],
    *,
    equity_broker: EquityBrokerAdapter,
    bank_buffer_usd: float = DEFAULT_BANK_BUFFER_USD,
    profit_return_threshold_usd: float = DEFAULT_PROFIT_RETURN_THRESHOLD_USD,
    ledger_path: Path | None = None,
    tax_rate: float = DEFAULT_QUALIFIED_DIVIDEND_TAX_RATE,
) -> dict[str, Any]:
    """Run a single step. Mutates and returns the state dict; caller persists it.

    Transfers are logged to the durable transfer ledger so remittance_status.py
    can compute after-tax progress toward the $1000/mo bank-deposit target.
    """

    now = datetime.now(timezone.utc).isoformat()
    balance = bank.get_balance()
    surplus = balance.available_usd - bank_buffer_usd

    # Determine if this is a paper/dry-run adapter
    dry_run = isinstance(bank, PaperBankAdapter)

    if surplus > 0:
        transfer = bank.send_to_broker(surplus, idempotency_key=str(uuid.uuid4()))
        state["events"].append({"type": "withdraw", "at": now, **asdict(transfer)})
        if transfer.success:
            state["principal_deployed_usd"] += surplus
            for order in strategy.plan_purchase(surplus):
                buy_result = equity_broker.buy(order.symbol, order.notional_usd)
                state["events"].append({"type": "dca_buy", "at": now, **asdict(buy_result)})
            _log_transfer(
                direction=TransferDirection.MERCURY_TO_BROKER,
                amount_usd=surplus,
                success=True,
                dry_run=dry_run,
                reason="income_loop_fund_broker",
                ledger_path=ledger_path,
            )
        else:
            _log_transfer(
                direction=TransferDirection.MERCURY_TO_BROKER,
                amount_usd=surplus,
                success=False,
                dry_run=dry_run,
                reason="income_loop_fund_broker_failed",
                ledger_path=ledger_path,
            )
    else:
        logger.info("No surplus above the $%.2f buffer; nothing to withdraw", bank_buffer_usd)

    dividend_income = equity_broker.collect_dividend_income()
    if dividend_income.total_usd > 0:
        # Dividends are qualified-dividend income (SCHD), taxed at the
        # qualified-dividend rate, not ordinary income rates.
        state["realized_profit_usd"] += dividend_income.total_usd
        state["realized_pre_tax_pnl_usd"] += dividend_income.total_usd
        state["events"].append(
            {
                "type": "dividend_income_collected",
                "at": now,
                "amount_usd": dividend_income.total_usd,
                "tax_rate": tax_rate,
                "after_tax_estimate": round(
                    estimate_after_tax_profit(
                        dividend_income.total_usd, tax_rate=tax_rate
                    ),
                    2,
                ),
            }
        )

    if state["realized_profit_usd"] >= profit_return_threshold_usd:
        payout = state["realized_profit_usd"]
        transfer = bank.record_incoming_from_broker(payout)
        state["events"].append({"type": "deposit", "at": now, **asdict(transfer)})
        if transfer.success:
            state["realized_profit_usd"] = 0.0
            _log_transfer(
                direction=TransferDirection.BROKER_TO_MERCURY,
                amount_usd=payout,
                success=True,
                dry_run=dry_run,
                reason="income_loop_remit_profit",
                ledger_path=ledger_path,
            )
        else:
            _log_transfer(
                direction=TransferDirection.BROKER_TO_MERCURY,
                amount_usd=payout,
                success=False,
                dry_run=dry_run,
                reason="income_loop_remit_profit_failed",
                ledger_path=ledger_path,
            )

    # Compute remittance progress toward $1000/mo after-tax target
    records = load_transfer_ledger(ledger_path=ledger_path) if ledger_path else []
    progress = compute_remittance_progress(
        records,
        target_usd=MONTHLY_AFTER_TAX_TARGET_USD,
        realized_pre_tax_pnl_usd=state.get("realized_pre_tax_pnl_usd"),
        tax_rate=tax_rate,
    )
    state["remittance_progress"] = progress.as_dict()

    return state


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-path", type=Path, default=DEFAULT_STATE_PATH)
    parser.add_argument("--ledger-path", type=Path, default=DEFAULT_LEDGER_PATH)
    parser.add_argument("--paper-starting-balance", type=float, default=0.0)
    parser.add_argument("--bank-buffer-usd", type=float, default=DEFAULT_BANK_BUFFER_USD)
    parser.add_argument(
        "--profit-return-threshold-usd", type=float, default=DEFAULT_PROFIT_RETURN_THRESHOLD_USD
    )
    parser.add_argument(
        "--tax-rate",
        type=float,
        default=DEFAULT_QUALIFIED_DIVIDEND_TAX_RATE,
        help="Tax rate for after-tax profit estimation (default: 15%% qualified dividend rate)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Use MercuryBankAdapter + AlpacaEquityBrokerAdapter (requires explicit env vars)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output summary as JSON (default: human-readable summary)",
    )
    return parser.parse_args()


def _build_adapters(live: bool) -> tuple[BankAdapter, EquityBrokerAdapter]:
    """Construct adapters. Paper by default; live requires explicit env vars."""
    if live:
        from src.adapters.bank_adapter import MercuryBankAdapter
        from src.adapters.equity_broker_adapter import AlpacaEquityBrokerAdapter

        # MercuryBankAdapter requires MERCURY_API_TOKEN, MERCURY_ACCOUNT_ID,
        # and MERCURY_LIVE_TRANSFERS_ENABLED=1. AlpacaEquityBrokerAdapter requires
        # DIVIDEND_GROWTH_ALPACA_API_KEY, DIVIDEND_GROWTH_ALPACA_API_SECRET,
        # and DIVIDEND_GROWTH_ALPACA_ENABLED=1.
        # from_env() raises if any are missing - fail closed, never construct
        # with defaults that could move real money.
        recipient_id = __import__("os").environ.get("MERCURY_RECIPIENT_ID", "")
        bank = MercuryBankAdapter.from_env(recipient_id=recipient_id)
        equity_broker = AlpacaEquityBrokerAdapter.from_env()
    else:
        bank = PaperBankAdapter(starting_balance_usd=0.0)
        equity_broker = PaperEquityBrokerAdapter()
    return bank, equity_broker


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    args = parse_args()

    bank, equity_broker = _build_adapters(live=args.live)
    strategy = DividendGrowthStrategy()
    state = _load_state(args.state_path)

    # For paper mode, set the starting balance on the bank adapter
    if not args.live and isinstance(bank, PaperBankAdapter):
        bank._balance = args.paper_starting_balance

    state = run_once(
        bank,
        strategy,
        state,
        equity_broker=equity_broker,
        bank_buffer_usd=args.bank_buffer_usd,
        profit_return_threshold_usd=args.profit_return_threshold_usd,
        ledger_path=args.ledger_path,
        tax_rate=args.tax_rate,
    )

    _save_state(args.state_path, state)

    # Print summary (not full state - that's too verbose for daily runs)
    progress = state.get("remittance_progress", {})
    summary = {
        "principal_deployed_usd": state["principal_deployed_usd"],
        "realized_profit_usd": state["realized_profit_usd"],
        "realized_pre_tax_pnl_usd": state.get("realized_pre_tax_pnl_usd", 0.0),
        "remittance_progress": progress,
        "events_count": len(state["events"]),
    }
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"principal_deployed: ${summary['principal_deployed_usd']:.2f}")
        print(f"realized_profit: ${summary['realized_profit_usd']:.2f}")
        rp = summary["remittance_progress"]
        print(
            f"remittance: ${rp.get('remitted_to_bank_usd', 0)} / "
            f"${rp.get('target_usd', 0)} target_met={rp.get('target_met', False)}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
