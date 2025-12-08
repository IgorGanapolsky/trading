#!/usr/bin/env python3
"""
Daily Position Reconciliation - Alpaca <-> Local State Sync

Ensures our local system_state.json matches Alpaca's ground truth.
Run daily to detect and fix discrepancies.

Checks:
1. Position quantities match
2. P/L calculations are accurate
3. No phantom positions (in local but not Alpaca)
4. No missing positions (in Alpaca but not local)
5. Account equity matches

Critical gap addressed:
- "Did Alpaca fuck us?" - CEO concern Dec 8, 2025
- Local state showed $17.49 P/L but hook showed $5.5
- No reconciliation between systems

Usage:
    python scripts/reconcile_positions.py
    python scripts/reconcile_positions.py --fix  # Auto-fix discrepancies
    python scripts/reconcile_positions.py --report-only  # Just report, no changes

Author: Trading System CTO
Created: 2025-12-08
"""

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass
class PositionDiff:
    """Difference between local and Alpaca position."""
    symbol: str
    local_qty: float
    alpaca_qty: float
    local_value: float
    alpaca_value: float
    qty_diff: float
    value_diff: float
    status: str  # 'match', 'mismatch', 'missing_local', 'missing_alpaca'


@dataclass
class ReconciliationReport:
    """Full reconciliation report."""
    timestamp: datetime
    local_equity: float
    alpaca_equity: float
    equity_diff: float
    local_pl: float
    alpaca_pl: float
    pl_diff: float
    position_diffs: list[PositionDiff]
    discrepancies: list[str]
    fixes_applied: list[str]
    is_reconciled: bool


class PositionReconciler:
    """
    Reconcile positions between local state and Alpaca.
    """

    # Tolerance for floating point comparisons
    QTY_TOLERANCE = 0.0001
    VALUE_TOLERANCE = 0.01

    def __init__(
        self,
        state_path: Path = Path("data/system_state.json"),
        auto_fix: bool = False,
    ):
        """
        Initialize reconciler.

        Args:
            state_path: Path to local system state
            auto_fix: Whether to automatically fix discrepancies
        """
        self.state_path = state_path
        self.auto_fix = auto_fix
        self.client = None

        # Initialize Alpaca client
        self._init_alpaca()

    def _init_alpaca(self) -> None:
        """Initialize Alpaca client."""
        try:
            from alpaca.trading.client import TradingClient

            api_key = os.getenv("ALPACA_API_KEY")
            api_secret = os.getenv("ALPACA_SECRET_KEY")

            if not api_key or not api_secret:
                raise ValueError("ALPACA_API_KEY and ALPACA_SECRET_KEY required")

            self.client = TradingClient(api_key, api_secret, paper=True)
            logger.info("Alpaca client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Alpaca client: {e}")
            raise

    def reconcile(self) -> ReconciliationReport:
        """
        Perform full reconciliation.

        Returns:
            ReconciliationReport with all findings
        """
        logger.info("=" * 70)
        logger.info("POSITION RECONCILIATION")
        logger.info("=" * 70)

        discrepancies = []
        fixes_applied = []

        # Get Alpaca data (ground truth)
        alpaca_account = self.client.get_account()
        alpaca_positions = self.client.get_all_positions()

        alpaca_equity = float(alpaca_account.equity)
        alpaca_cash = float(alpaca_account.cash)
        starting_balance = 100000.0  # Known starting balance
        alpaca_pl = alpaca_equity - starting_balance

        logger.info(f"Alpaca Equity: ${alpaca_equity:,.2f}")
        logger.info(f"Alpaca P/L: ${alpaca_pl:,.2f}")
        logger.info(f"Alpaca Positions: {len(alpaca_positions)}")

        # Get local data
        local_state = self._load_local_state()
        local_equity = local_state.get("account", {}).get("current_equity", 0)
        local_pl = local_state.get("account", {}).get("total_pl", 0)
        local_positions = local_state.get("performance", {}).get("open_positions", [])

        logger.info(f"Local Equity: ${local_equity:,.2f}")
        logger.info(f"Local P/L: ${local_pl:,.2f}")
        logger.info(f"Local Positions: {len(local_positions)}")

        # Compare equity
        equity_diff = abs(alpaca_equity - local_equity)
        if equity_diff > self.VALUE_TOLERANCE:
            discrepancies.append(
                f"Equity mismatch: Local ${local_equity:,.2f} vs Alpaca ${alpaca_equity:,.2f} "
                f"(diff: ${equity_diff:,.2f})"
            )

        # Compare P/L
        pl_diff = abs(alpaca_pl - local_pl)
        if pl_diff > self.VALUE_TOLERANCE:
            discrepancies.append(
                f"P/L mismatch: Local ${local_pl:,.2f} vs Alpaca ${alpaca_pl:,.2f} "
                f"(diff: ${pl_diff:,.2f})"
            )

        # Compare positions
        position_diffs = self._compare_positions(local_positions, alpaca_positions)

        for diff in position_diffs:
            if diff.status != "match":
                discrepancies.append(
                    f"Position {diff.symbol}: {diff.status} - "
                    f"Local qty={diff.local_qty:.6f} vs Alpaca qty={diff.alpaca_qty:.6f}"
                )

        # Apply fixes if enabled
        if self.auto_fix and discrepancies:
            fixes_applied = self._apply_fixes(
                alpaca_equity=alpaca_equity,
                alpaca_pl=alpaca_pl,
                alpaca_positions=alpaca_positions,
                local_state=local_state,
            )

        # Create report
        is_reconciled = len(discrepancies) == 0 or (self.auto_fix and len(fixes_applied) > 0)

        report = ReconciliationReport(
            timestamp=datetime.now(),
            local_equity=local_equity,
            alpaca_equity=alpaca_equity,
            equity_diff=equity_diff,
            local_pl=local_pl,
            alpaca_pl=alpaca_pl,
            pl_diff=pl_diff,
            position_diffs=position_diffs,
            discrepancies=discrepancies,
            fixes_applied=fixes_applied,
            is_reconciled=is_reconciled,
        )

        self._log_report(report)
        self._save_report(report)

        return report

    def _load_local_state(self) -> dict:
        """Load local system state."""
        if not self.state_path.exists():
            logger.warning(f"Local state not found: {self.state_path}")
            return {}

        with open(self.state_path) as f:
            return json.load(f)

    def _compare_positions(
        self,
        local_positions: list[dict],
        alpaca_positions: list,
    ) -> list[PositionDiff]:
        """Compare positions between local and Alpaca."""
        diffs = []

        # Build lookup maps
        local_by_symbol = {p.get("symbol"): p for p in local_positions}
        alpaca_by_symbol = {p.symbol: p for p in alpaca_positions}

        all_symbols = set(local_by_symbol.keys()) | set(alpaca_by_symbol.keys())

        for symbol in all_symbols:
            local_pos = local_by_symbol.get(symbol)
            alpaca_pos = alpaca_by_symbol.get(symbol)

            if local_pos and alpaca_pos:
                # Both have position - compare
                local_qty = float(local_pos.get("quantity", 0))
                alpaca_qty = float(alpaca_pos.qty)
                local_value = float(local_pos.get("amount", 0))
                alpaca_value = float(alpaca_pos.market_value)

                qty_diff = abs(local_qty - alpaca_qty)
                value_diff = abs(local_value - alpaca_value)

                if qty_diff > self.QTY_TOLERANCE or value_diff > self.VALUE_TOLERANCE:
                    status = "mismatch"
                else:
                    status = "match"

                diffs.append(PositionDiff(
                    symbol=symbol,
                    local_qty=local_qty,
                    alpaca_qty=alpaca_qty,
                    local_value=local_value,
                    alpaca_value=alpaca_value,
                    qty_diff=qty_diff,
                    value_diff=value_diff,
                    status=status,
                ))

            elif local_pos and not alpaca_pos:
                # Local has position but Alpaca doesn't (phantom)
                diffs.append(PositionDiff(
                    symbol=symbol,
                    local_qty=float(local_pos.get("quantity", 0)),
                    alpaca_qty=0,
                    local_value=float(local_pos.get("amount", 0)),
                    alpaca_value=0,
                    qty_diff=float(local_pos.get("quantity", 0)),
                    value_diff=float(local_pos.get("amount", 0)),
                    status="missing_alpaca",
                ))

            elif alpaca_pos and not local_pos:
                # Alpaca has position but local doesn't (missing)
                diffs.append(PositionDiff(
                    symbol=symbol,
                    local_qty=0,
                    alpaca_qty=float(alpaca_pos.qty),
                    local_value=0,
                    alpaca_value=float(alpaca_pos.market_value),
                    qty_diff=float(alpaca_pos.qty),
                    value_diff=float(alpaca_pos.market_value),
                    status="missing_local",
                ))

        return diffs

    def _apply_fixes(
        self,
        alpaca_equity: float,
        alpaca_pl: float,
        alpaca_positions: list,
        local_state: dict,
    ) -> list[str]:
        """Apply fixes to sync local state with Alpaca."""
        fixes = []

        logger.info("Applying fixes to sync with Alpaca...")

        # Update account info
        local_state["account"]["current_equity"] = alpaca_equity
        local_state["account"]["total_pl"] = alpaca_pl
        local_state["account"]["total_pl_pct"] = (alpaca_pl / 100000.0) * 100

        fixes.append(f"Updated equity to ${alpaca_equity:,.2f}")
        fixes.append(f"Updated P/L to ${alpaca_pl:,.2f}")

        # Rebuild positions from Alpaca
        new_positions = []
        for pos in alpaca_positions:
            new_positions.append({
                "symbol": pos.symbol,
                "tier": "unknown",
                "amount": float(pos.market_value),
                "order_id": None,
                "entry_date": datetime.now().isoformat(),
                "entry_price": float(pos.avg_entry_price),
                "current_price": float(pos.current_price),
                "quantity": float(pos.qty),
                "unrealized_pl": float(pos.unrealized_pl),
                "unrealized_pl_pct": float(pos.unrealized_plpc) * 100,
                "last_updated": datetime.now().isoformat(),
            })

        local_state["performance"]["open_positions"] = new_positions
        fixes.append(f"Synced {len(new_positions)} positions from Alpaca")

        # Update positions value
        positions_value = sum(float(pos.market_value) for pos in alpaca_positions)
        local_state["account"]["positions_value"] = positions_value

        # Update timestamp
        local_state["meta"]["last_updated"] = datetime.now().isoformat()
        local_state["meta"]["last_reconciliation"] = datetime.now().isoformat()

        # Save updated state
        with open(self.state_path, "w") as f:
            json.dump(local_state, f, indent=2)

        logger.info(f"Applied {len(fixes)} fixes")
        return fixes

    def _log_report(self, report: ReconciliationReport) -> None:
        """Log reconciliation report."""
        logger.info("=" * 70)
        logger.info("RECONCILIATION REPORT")
        logger.info("=" * 70)

        if report.is_reconciled:
            logger.info("STATUS: RECONCILED")
        else:
            logger.warning(f"STATUS: {len(report.discrepancies)} DISCREPANCIES FOUND")

        logger.info(f"Equity Diff: ${report.equity_diff:,.2f}")
        logger.info(f"P/L Diff: ${report.pl_diff:,.2f}")

        if report.discrepancies:
            logger.warning("Discrepancies:")
            for d in report.discrepancies:
                logger.warning(f"  - {d}")

        if report.fixes_applied:
            logger.info("Fixes Applied:")
            for f in report.fixes_applied:
                logger.info(f"  - {f}")

        logger.info("=" * 70)

    def _save_report(self, report: ReconciliationReport) -> None:
        """Save reconciliation report to file."""
        report_dir = Path("data/reconciliation")
        report_dir.mkdir(parents=True, exist_ok=True)

        report_file = report_dir / f"reconciliation_{report.timestamp.strftime('%Y%m%d_%H%M%S')}.json"

        report_data = {
            "timestamp": report.timestamp.isoformat(),
            "local_equity": report.local_equity,
            "alpaca_equity": report.alpaca_equity,
            "equity_diff": report.equity_diff,
            "local_pl": report.local_pl,
            "alpaca_pl": report.alpaca_pl,
            "pl_diff": report.pl_diff,
            "position_diffs": [
                {
                    "symbol": d.symbol,
                    "local_qty": d.local_qty,
                    "alpaca_qty": d.alpaca_qty,
                    "status": d.status,
                }
                for d in report.position_diffs
            ],
            "discrepancies": report.discrepancies,
            "fixes_applied": report.fixes_applied,
            "is_reconciled": report.is_reconciled,
        }

        with open(report_file, "w") as f:
            json.dump(report_data, f, indent=2)

        logger.info(f"Report saved: {report_file}")


def main():
    parser = argparse.ArgumentParser(description="Reconcile positions with Alpaca")
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Auto-fix discrepancies by syncing with Alpaca",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Only generate report, don't modify anything",
    )
    args = parser.parse_args()

    try:
        reconciler = PositionReconciler(auto_fix=args.fix and not args.report_only)
        report = reconciler.reconcile()

        # Exit with error if discrepancies found and not fixed
        if not report.is_reconciled:
            logger.error("Reconciliation found discrepancies!")
            sys.exit(1)
        else:
            logger.info("Reconciliation complete - all positions match")
            sys.exit(0)

    except Exception as e:
        logger.error(f"Reconciliation failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
