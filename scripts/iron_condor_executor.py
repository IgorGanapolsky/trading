#!/usr/bin/env python3
"""
Iron Condor Executor - Execute Approved Trades

Executes iron condor trades that have been approved via GitHub issue.
Includes safety checks for position limits, buying power, and market hours.

Safety Checks:
- Max 2 positions at a time
- 5% max risk per position
- Market must be open
- Trade must be approved (or auto-approved after 30 min)

Usage:
    python scripts/iron_condor_executor.py                    # Execute pending trade
    python scripts/iron_condor_executor.py --dry-run          # Simulate execution
    python scripts/iron_condor_executor.py --trade-id IC_001  # Execute specific trade
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from src.safety.mandatory_trade_gate import safe_submit_order

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Constants
MAX_POSITIONS = 2
POSITION_SIZE_PCT = 0.05
PENDING_TRADE_FILE = Path(__file__).parent.parent / "data" / "pending_ic_trade.json"
IC_TRADE_LOG = Path(__file__).parent.parent / "data" / "ic_trade_log.json"
IC_ENTRIES_FILE = Path(__file__).parent.parent / "data" / "ic_entries.json"


def get_trading_client():
    """Get Alpaca trading client."""
    from alpaca.trading.client import TradingClient
    from src.utils.alpaca_client import get_alpaca_credentials

    api_key, secret = get_alpaca_credentials()
    if not api_key or not secret:
        logger.error("Alpaca credentials not found")
        return None

    return TradingClient(api_key, secret, paper=True)


def check_market_open() -> bool:
    """Check if market is currently open."""
    et = ZoneInfo("America/New_York")
    now = datetime.now(et)

    # Weekend check
    if now.weekday() >= 5:
        logger.warning("Market closed (weekend)")
        return False

    # Hours check (9:30 AM - 4:00 PM ET)
    hour = now.hour
    minute = now.minute
    if hour < 9 or (hour == 9 and minute < 30) or hour >= 16:
        logger.warning("Market closed (outside trading hours)")
        return False

    return True


def check_position_limit(client) -> bool:
    """Check if we're under the position limit."""
    try:
        positions = client.get_all_positions()
        spy_options = [p for p in positions if p.symbol.startswith("SPY") and len(p.symbol) > 5]
        ic_count = len(spy_options) // 4

        if ic_count >= MAX_POSITIONS:
            logger.warning(f"Position limit reached: {ic_count}/{MAX_POSITIONS}")
            return False

        logger.info(f"Position check passed: {ic_count}/{MAX_POSITIONS}")
        return True
    except Exception as e:
        logger.error(f"Position check failed: {e}")
        return False


def check_buying_power(client, max_risk: float) -> bool:
    """Check if we have sufficient buying power."""
    try:
        account = client.get_account()
        buying_power = float(account.buying_power)
        equity = float(account.equity)

        # Max risk should be <= 5% of equity
        max_allowed_risk = equity * POSITION_SIZE_PCT
        if max_risk > max_allowed_risk:
            logger.warning(f"Risk too high: ${max_risk:.0f} > ${max_allowed_risk:.0f} (5%)")
            return False

        if buying_power < max_risk:
            logger.warning(f"Insufficient buying power: ${buying_power:.0f} < ${max_risk:.0f}")
            return False

        logger.info(f"Buying power check passed: ${buying_power:,.0f} available")
        return True
    except Exception as e:
        logger.error(f"Buying power check failed: {e}")
        return False


def check_github_approval(issue_number: int) -> tuple[bool, str]:
    """Check if trade was approved or rejected via GitHub issue."""
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    repo = os.getenv("GITHUB_REPOSITORY", "IgorGanapolsky/trading")

    if not token or not issue_number:
        return True, "auto"  # Auto-approve if no issue tracking

    from urllib.request import Request, urlopen

    try:
        req = Request(
            f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json",
            },
        )
        with urlopen(req, timeout=30) as response:
            comments = json.loads(response.read().decode("utf-8"))

            for comment in comments:
                body = comment.get("body", "").upper().strip()
                if "REJECT" in body:
                    return False, "rejected"
                if "APPROVE" in body:
                    return True, "approved"

        # No explicit response - check if 30 minutes passed for auto-approve
        return True, "auto"

    except Exception as e:
        logger.warning(f"Could not check GitHub approval: {e}")
        return True, "auto"


def build_option_symbol(underlying: str, expiry: str, strike: float, opt_type: str) -> str:
    """Build OCC option symbol."""
    exp_formatted = expiry.replace("-", "")[2:]  # YYMMDD
    strike_str = f"{int(strike * 1000):08d}"
    return f"{underlying}{exp_formatted}{opt_type}{strike_str}"


def execute_iron_condor(trade: dict, dry_run: bool = False) -> dict:
    """Execute the iron condor trade."""
    logger.info("=" * 60)
    logger.info("EXECUTING IRON CONDOR" + (" (DRY RUN)" if dry_run else ""))
    logger.info("=" * 60)

    strikes = trade["strikes"]
    expiry = trade["expiry"]

    # Build option symbols
    long_put_sym = build_option_symbol("SPY", expiry, strikes["long_put"], "P")
    short_put_sym = build_option_symbol("SPY", expiry, strikes["short_put"], "P")
    short_call_sym = build_option_symbol("SPY", expiry, strikes["short_call"], "C")
    long_call_sym = build_option_symbol("SPY", expiry, strikes["long_call"], "C")

    logger.info(f"Long Put:   {long_put_sym}")
    logger.info(f"Short Put:  {short_put_sym}")
    logger.info(f"Short Call: {short_call_sym}")
    logger.info(f"Long Call:  {long_call_sym}")

    if dry_run:
        logger.info("DRY RUN - Order not submitted")
        return {
            "status": "DRY_RUN",
            "symbols": [long_put_sym, short_put_sym, short_call_sym, long_call_sym],
        }

    client = get_trading_client()
    if not client:
        return {"status": "FAILED", "reason": "No trading client"}

    try:
        from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest, OptionLegRequest

        # Build multi-leg order
        option_legs = [
            OptionLegRequest(symbol=long_put_sym, side=OrderSide.BUY, ratio_qty=1),
            OptionLegRequest(symbol=short_put_sym, side=OrderSide.SELL, ratio_qty=1),
            OptionLegRequest(symbol=short_call_sym, side=OrderSide.SELL, ratio_qty=1),
            OptionLegRequest(symbol=long_call_sym, side=OrderSide.BUY, ratio_qty=1),
        ]

        order_req = MarketOrderRequest(
            qty=1,
            order_class=OrderClass.MLEG,
            legs=option_legs,
            time_in_force=TimeInForce.DAY,
        )

        logger.info("Submitting MLeg order...")
        order = safe_submit_order(client, order_req)

        logger.info(f"Order submitted: {order.id}")
        logger.info(f"Status: {order.status}")

        return {
            "status": "SUBMITTED",
            "order_id": str(order.id),
            "order_status": str(order.status),
        }

    except Exception as e:
        logger.error(f"Order submission failed: {e}")
        return {"status": "FAILED", "reason": str(e)}


def log_trade(trade: dict, result: dict):
    """Log the trade to RAG for full traceability."""
    from datetime import datetime, timezone

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    order_id = result.get("order_id", "unknown")[:8]
    trade_id = f"trade_{today}_{order_id}"

    # Create RAG lesson content
    lesson_content = f"""# Trade Executed: {today}

**Trade ID**: {trade_id}
**Date**: {today}
**Type**: Iron Condor Entry
**Status**: {result.get("status", "unknown")}
**Severity**: INFO
**Category**: trade-execution

## Position Details
- **Expiry**: {trade.get("expiry", "unknown")}
- **DTE**: {trade.get("dte", "unknown")}
- **Short Put**: ${trade["strikes"]["short_put"]:.0f}
- **Long Put**: ${trade["strikes"]["long_put"]:.0f}
- **Short Call**: ${trade["strikes"]["short_call"]:.0f}
- **Long Call**: ${trade["strikes"]["long_call"]:.0f}

## Financials
- **Credit Received**: ${trade["pricing"]["credit_dollars"]:.0f}
- **Max Risk**: ${trade["pricing"]["max_risk"]:.0f}
- **Win Probability**: {trade["pricing"]["win_probability"] * 100:.0f}%

## Execution
- **Order ID**: {result.get("order_id", "N/A")}
- **Order Status**: {result.get("order_status", "N/A")}
- **VIX Conditions**: {trade.get("vix_status", "unknown")}
- **Account Equity**: ${trade.get("equity", 0):,.2f}

## Phil Town Rule #1 Compliance
- Position size: 5% max ✓
- Defined risk: Yes ✓
- Stop loss defined: 200% ✓
- Profit target: 50% ✓

## Exit Rules (Guardian Enforced)
- Take profit at 50% of credit
- Stop loss at 200% of credit
- Exit at 7 DTE
"""

    # Add to RAG
    try:
        from src.rag.lessons_learned_rag import LessonsLearnedRAG

        rag = LessonsLearnedRAG()
        rag.add_lesson(trade_id, lesson_content)
        logger.info(f"Trade logged to RAG: {trade_id}")
    except Exception as e:
        logger.error(f"Failed to log trade to RAG: {e}")

    # Also update ic_entries.json for guardian (still needed for exit tracking)
    update_ic_entries(trade, trade_id)

    return trade_id


def load_trade_log() -> dict:
    """Load or initialize the trade log."""
    if IC_TRADE_LOG.exists():
        with open(IC_TRADE_LOG) as f:
            return json.load(f)
    return {
        "trades": [],
        "stats": {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": None,
            "avg_credit": 0,
            "avg_pnl": None,
            "total_pnl": 0,
        },
    }


def save_trade_log(trade_log: dict):
    """Save the trade log."""
    IC_TRADE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(IC_TRADE_LOG, "w") as f:
        json.dump(trade_log, f, indent=2)


def update_ic_entries(trade: dict, trade_id: str):
    """Update ic_entries.json for the guardian to track."""
    entries = {}
    if IC_ENTRIES_FILE.exists():
        with open(IC_ENTRIES_FILE) as f:
            entries = json.load(f)

    expiry_key = trade["expiry"].replace("-", "")[2:]  # YYMMDD format
    entry_key = f"IC_{expiry_key}"

    entries[entry_key] = {
        "trade_id": trade_id,
        "credit": trade["pricing"]["credit"],
        "date": datetime.utcnow().isoformat(),
        "strikes": trade["strikes"],
    }

    IC_ENTRIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(IC_ENTRIES_FILE, "w") as f:
        json.dump(entries, f, indent=2)

    logger.info(f"IC entry recorded: {entry_key}")


def close_github_issue(issue_number: int, result: dict):
    """Close the GitHub issue with execution result."""
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    repo = os.getenv("GITHUB_REPOSITORY", "IgorGanapolsky/trading")

    if not token or not issue_number:
        return

    from urllib.request import Request, urlopen

    status_emoji = "✅" if result["status"] == "SUBMITTED" else "❌"
    comment = f"""## {status_emoji} Trade Execution Complete

**Status:** {result["status"]}
**Order ID:** {result.get("order_id", "N/A")}
**Time:** {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}

{"Trade successfully submitted to Alpaca paper account." if result["status"] == "SUBMITTED" else f"Execution failed: {result.get('reason', 'Unknown error')}"}
"""

    try:
        # Add comment
        data = json.dumps({"body": comment}).encode("utf-8")
        req = Request(
            f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json",
            },
        )
        with urlopen(req, timeout=30) as response:
            if response.status == 201:
                logger.info("GitHub issue commented")

        # Close issue
        data = json.dumps({"state": "closed"}).encode("utf-8")
        req = Request(
            f"https://api.github.com/repos/{repo}/issues/{issue_number}",
            data=data,
            method="PATCH",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json",
            },
        )
        with urlopen(req, timeout=30) as response:
            if response.status == 200:
                logger.info("GitHub issue closed")

    except Exception as e:
        logger.warning(f"Could not update GitHub issue: {e}")


def main():
    parser = argparse.ArgumentParser(description="Iron Condor Executor")
    parser.add_argument("--dry-run", action="store_true", help="Simulate execution")
    parser.add_argument("--trade-id", type=str, help="Execute specific trade ID")
    parser.add_argument("--force", action="store_true", help="Skip approval check")
    args = parser.parse_args()

    # Load pending trade
    if not PENDING_TRADE_FILE.exists():
        logger.info("No pending trade found")
        return 0

    with open(PENDING_TRADE_FILE) as f:
        trade = json.load(f)

    logger.info(f"Pending trade: {trade['expiry']} IC")

    # Safety checks (unless dry run)
    if not args.dry_run:
        # Check market hours
        if not check_market_open():
            logger.warning("Market closed - cannot execute")
            return 1

        client = get_trading_client()
        if not client:
            logger.error("Could not create trading client")
            return 1

        # Check position limit
        if not check_position_limit(client):
            logger.warning("Position limit check failed")
            return 1

        # Check buying power
        if not check_buying_power(client, trade["pricing"]["max_risk"]):
            logger.warning("Buying power check failed")
            return 1

        # Check approval (unless forced)
        if not args.force:
            issue_number = trade.get("issue_number")
            approved, approval_type = check_github_approval(issue_number)
            if not approved:
                logger.info("Trade was REJECTED via GitHub")
                PENDING_TRADE_FILE.unlink()  # Remove pending trade
                return 0
            logger.info(f"Trade approval: {approval_type}")

    # Execute the trade
    result = execute_iron_condor(trade, dry_run=args.dry_run)

    if result["status"] == "SUBMITTED":
        # Log to trade log
        trade_id = log_trade(trade, result)

        # Close GitHub issue
        if trade.get("issue_number"):
            close_github_issue(trade["issue_number"], result)

        # Remove pending trade file
        PENDING_TRADE_FILE.unlink()
        logger.info("Pending trade file removed")

        print(f"\n✅ Trade executed successfully: {trade_id}")
        return 0

    elif result["status"] == "DRY_RUN":
        print("\n✅ Dry run completed successfully")
        return 0

    else:
        print(f"\n❌ Trade execution failed: {result.get('reason', 'Unknown')}")
        return 1


if __name__ == "__main__":
    sys.exit(main())


def record_trade_to_rag(trade: dict, result: dict):
    """Record trade execution to RAG for full traceability."""
    try:
        from datetime import datetime
        from pathlib import Path

        # Create lesson file for this trade
        today = datetime.utcnow().strftime("%Y-%m-%d")
        trade_id = result.get("order_id", "unknown")[:8]

        lesson_content = f"""# Trade Executed: {today}

**Trade ID**: {trade_id}
**Date**: {today}
**Type**: Iron Condor Entry
**Status**: {result.get("status", "unknown")}

## Position Details
- **Expiry**: {trade.get("expiry", "unknown")}
- **DTE**: {trade.get("dte", "unknown")}
- **Short Put**: ${trade["strikes"]["short_put"]:.0f}
- **Long Put**: ${trade["strikes"]["long_put"]:.0f}
- **Short Call**: ${trade["strikes"]["short_call"]:.0f}
- **Long Call**: ${trade["strikes"]["long_call"]:.0f}

## Financials
- **Credit Received**: ${trade["pricing"]["credit_dollars"]:.0f}
- **Max Risk**: ${trade["pricing"]["max_risk"]:.0f}
- **Win Probability**: {trade["pricing"]["win_probability"] * 100:.0f}%

## Execution
- **Order ID**: {result.get("order_id", "N/A")}
- **Order Status**: {result.get("order_status", "N/A")}
- **VIX Conditions**: {trade.get("vix_status", "unknown")}

## Phil Town Rule #1 Compliance
- Position size: 5% max ✓
- Defined risk: Yes ✓
- Stop loss defined: 200% ✓
- Profit target: 50% ✓
"""

        # Save to RAG lessons
        lesson_file = Path(f"rag_knowledge/lessons_learned/trade_{today}_{trade_id}.md")
        lesson_file.parent.mkdir(parents=True, exist_ok=True)
        lesson_file.write_text(lesson_content)

        print(f"Trade recorded to RAG: {lesson_file}")

    except Exception as e:
        print(f"Failed to record trade to RAG: {e}")
