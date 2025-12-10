#!/usr/bin/env python3
"""
T-Bill Ladder for Idle Cash

Converts idle cash to short-term Treasury bills earning 4.3-4.5% APY
instead of 0% sitting as cash drag in the brokerage account.

Strategy:
- Invests idle cash into BIL (SPDR Bloomberg 1-3 Month T-Bill ETF)
- Maintains 5% emergency cash reserve
- Runs weekly on Mondays to capture new T-bill issuance
- Near-zero credit risk, extremely high liquidity

Expected Returns:
- Current 4-week T-bill yield: ~4.4% APY
- On $20k idle cash: ~$880/year = $2.40/day FREE MONEY
- At scale ($75k): ~$3,300/year = $9/day additional income

Usage:
    # Execute weekly T-bill investment
    python scripts/tbill_ladder.py --execute

    # Check current cash allocation
    python scripts/tbill_ladder.py --status

    # Dry run (no actual trades)
    python scripts/tbill_ladder.py --dry-run

Author: Trading System CTO
Created: 2025-12-03
"""

import argparse
import json
import logging
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.alpaca_trader import AlpacaTrader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass
class TBillLadderStatus:
    """T-Bill ladder status and allocation."""

    timestamp: datetime
    total_equity: float
    cash_balance: float
    bil_position_value: float  # Current BIL holdings
    tbill_yield_estimate: float  # Estimated current yield
    cash_as_pct_of_equity: float
    bil_as_pct_of_equity: float
    investable_cash: float  # Cash available after reserve
    emergency_reserve: float  # Cash to keep in reserve
    recommended_investment: float  # Amount to invest in BIL
    action_required: bool


# T-Bill ladder configuration
TBILL_ETF = "BIL"  # SPDR Bloomberg 1-3 Month T-Bill ETF
EMERGENCY_RESERVE_PCT = 0.05  # Keep 5% as true cash
MIN_INVESTMENT_THRESHOLD = 100.0  # Minimum $100 to invest
CURRENT_TBILL_YIELD = 0.044  # ~4.4% APY estimate


def get_account_status(trader: AlpacaTrader) -> dict[str, Any]:
    """
    Get current account status including cash and positions.

    Returns:
        dict: Account details with equity, cash, and positions
    """
    try:
        account = trader.get_account_summary()
        positions = trader.get_positions()

        # Find BIL position if any
        bil_position = None
        for pos in positions:
            if pos.get("symbol") == TBILL_ETF:
                bil_position = pos
                break

        bil_value = float(bil_position["market_value"]) if bil_position else 0.0

        return {
            "equity": float(account.get("equity", 0)),
            "cash": float(account.get("cash", 0)),
            "buying_power": float(account.get("buying_power", 0)),
            "bil_position": bil_position,
            "bil_value": bil_value,
            "positions_count": len(positions),
        }

    except Exception as e:
        logger.error(f"Failed to get account status: {e}")
        return {
            "error": str(e),
            "equity": 0,
            "cash": 0,
            "bil_value": 0,
        }


def calculate_ladder_status(account: dict[str, Any]) -> TBillLadderStatus:
    """
    Calculate T-Bill ladder status and recommendations.

    Args:
        account: Account status from get_account_status()

    Returns:
        TBillLadderStatus with analysis and recommendations
    """
    equity = account.get("equity", 0)
    cash = account.get("cash", 0)
    bil_value = account.get("bil_value", 0)

    # Calculate percentages
    cash_pct = (cash / equity * 100) if equity > 0 else 0
    bil_pct = (bil_value / equity * 100) if equity > 0 else 0

    # Calculate emergency reserve (5% of equity)
    emergency_reserve = equity * EMERGENCY_RESERVE_PCT

    # Investable cash = current cash - emergency reserve
    investable_cash = max(0, cash - emergency_reserve)

    # Determine if action is required
    action_required = investable_cash >= MIN_INVESTMENT_THRESHOLD

    # Recommended investment (all investable cash goes to BIL)
    recommended_investment = investable_cash if action_required else 0

    return TBillLadderStatus(
        timestamp=datetime.now(),
        total_equity=equity,
        cash_balance=cash,
        bil_position_value=bil_value,
        tbill_yield_estimate=CURRENT_TBILL_YIELD,
        cash_as_pct_of_equity=cash_pct,
        bil_as_pct_of_equity=bil_pct,
        investable_cash=investable_cash,
        emergency_reserve=emergency_reserve,
        recommended_investment=recommended_investment,
        action_required=action_required,
    )


def execute_tbill_investment(
    trader: AlpacaTrader,
    amount: float,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Execute T-Bill (BIL) investment.

    Args:
        trader: AlpacaTrader instance
        amount: Dollar amount to invest
        dry_run: If True, don't actually execute trade

    Returns:
        dict: Execution result
    """
    logger.info(f"{'[DRY RUN] ' if dry_run else ''}Investing ${amount:.2f} in {TBILL_ETF}")

    if dry_run:
        return {
            "success": True,
            "dry_run": True,
            "symbol": TBILL_ETF,
            "amount": amount,
            "estimated_annual_yield": amount * CURRENT_TBILL_YIELD,
            "estimated_daily_income": amount * CURRENT_TBILL_YIELD / 365,
        }

    try:
        order = trader.execute_order(
            symbol=TBILL_ETF,
            amount_usd=amount,
            side="buy",
            tier="T1_CORE",  # Treat as core allocation
        )

        return {
            "success": True,
            "order": order,
            "symbol": TBILL_ETF,
            "amount": amount,
            "order_id": order.get("id"),
            "estimated_annual_yield": amount * CURRENT_TBILL_YIELD,
            "estimated_daily_income": amount * CURRENT_TBILL_YIELD / 365,
        }

    except Exception as e:
        logger.error(f"Failed to execute T-Bill investment: {e}")
        return {
            "success": False,
            "error": str(e),
            "symbol": TBILL_ETF,
            "amount": amount,
        }


def print_status_report(status: TBillLadderStatus) -> None:
    """Print formatted status report."""
    print("\n" + "=" * 70)
    print("T-BILL LADDER STATUS REPORT")
    print("=" * 70)
    print(f"Timestamp: {status.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 70)

    print("\nACCOUNT SUMMARY:")
    print(f"  Total Equity: ${status.total_equity:,.2f}")
    print(f"  Cash Balance: ${status.cash_balance:,.2f} ({status.cash_as_pct_of_equity:.1f}%)")
    print(f"  BIL Position: ${status.bil_position_value:,.2f} ({status.bil_as_pct_of_equity:.1f}%)")

    print("\nT-BILL LADDER ANALYSIS:")
    print(f"  Emergency Reserve (5%): ${status.emergency_reserve:,.2f}")
    print(f"  Investable Cash: ${status.investable_cash:,.2f}")
    print(f"  Estimated T-Bill Yield: {status.tbill_yield_estimate * 100:.2f}% APY")

    print("\nPROJECTED INCOME FROM T-BILLS:")
    current_tbill_income = status.bil_position_value * CURRENT_TBILL_YIELD
    print(f"  Current BIL Annual Yield: ${current_tbill_income:,.2f}/year")
    print(f"  Current BIL Daily Income: ${current_tbill_income / 365:.2f}/day")

    if status.action_required:
        additional_income = status.recommended_investment * CURRENT_TBILL_YIELD
        print(f"\n  With ${status.recommended_investment:,.2f} investment:")
        print(f"    Additional Annual Yield: ${additional_income:,.2f}/year")
        print(f"    Additional Daily Income: ${additional_income / 365:.2f}/day")

    print("\nRECOMMENDATION:")
    if status.action_required:
        print(f"  ACTION REQUIRED: Invest ${status.recommended_investment:,.2f} in {TBILL_ETF}")
        print(f"  This converts cash drag to {CURRENT_TBILL_YIELD * 100:.1f}% yielding T-Bills")
    else:
        print(
            f"  No action needed. Investable cash (${status.investable_cash:.2f}) below minimum (${MIN_INVESTMENT_THRESHOLD})"
        )

    print("=" * 70 + "\n")


def save_status_to_file(status: TBillLadderStatus, output_path: Path) -> None:
    """Save status to JSON file."""
    status_dict = asdict(status)
    status_dict["timestamp"] = status.timestamp.isoformat()

    with open(output_path, "w") as f:
        json.dump(status_dict, f, indent=2, default=str)

    logger.info(f"Status saved to {output_path}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="T-Bill Ladder for Idle Cash")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute T-Bill investment",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show current status only",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate execution without actual trades",
    )
    parser.add_argument(
        "--paper",
        action="store_true",
        default=True,
        help="Use paper trading (default: True)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/tbill_ladder_status.json",
        help="Output file path for status JSON",
    )

    args = parser.parse_args()

    try:
        # Initialize Alpaca trader
        trader = AlpacaTrader(paper=args.paper)

        # Get account status
        account = get_account_status(trader)

        if account.get("error"):
            logger.error(f"Failed to get account status: {account['error']}")
            sys.exit(1)

        # Calculate ladder status
        status = calculate_ladder_status(account)

        # Print status report
        print_status_report(status)

        # Save status to file
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        save_status_to_file(status, output_path)

        # Execute if requested and action required
        if args.execute or args.dry_run:
            if status.action_required:
                result = execute_tbill_investment(
                    trader=trader,
                    amount=status.recommended_investment,
                    dry_run=args.dry_run,
                )

                print("\nEXECUTION RESULT:")
                print("-" * 40)
                if result["success"]:
                    print(f"  Status: SUCCESS{'(DRY RUN)' if args.dry_run else ''}")
                    print(f"  Symbol: {result['symbol']}")
                    print(f"  Amount: ${result['amount']:,.2f}")
                    if not args.dry_run and result.get("order_id"):
                        print(f"  Order ID: {result['order_id']}")
                    print(f"  Estimated Annual Yield: ${result['estimated_annual_yield']:,.2f}")
                    print(f"  Estimated Daily Income: ${result['estimated_daily_income']:.2f}")
                else:
                    print("  Status: FAILED")
                    print(f"  Error: {result.get('error', 'Unknown error')}")
                print("-" * 40)
            else:
                print("\nNo investment needed - insufficient investable cash")

        sys.exit(0)

    except Exception as e:
        logger.error(f"T-Bill ladder script failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
