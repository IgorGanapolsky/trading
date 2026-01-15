#!/usr/bin/env python3
"""
Session Start Report - Verify all data sources match Alpaca (source of truth).

This script:
1. Queries Alpaca Paper $5K account
2. Queries Alpaca Brokerage account
3. Checks Progress Dashboard
4. Queries DialogFlow
5. Compares all sources and reports discrepancies

Alpaca is the SINGLE SOURCE OF TRUTH.

Usage:
    python3 scripts/session_start_report.py
"""

import json
import os
import sys
import urllib.request
import urllib.error
import ssl
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class SessionStartReport:
    """Generate session start verification report."""

    def __init__(self):
        """Initialize report generator."""
        self.paper_key = os.environ.get("ALPACA_PAPER_TRADING_5K_API_KEY", "")
        self.paper_secret = os.environ.get("ALPACA_PAPER_TRADING_5K_API_SECRET", "")
        self.broker_key = os.environ.get("ALPACA_BROKERAGE_TRADING_API_KEY", "")
        self.broker_secret = os.environ.get("ALPACA_BROKERAGE_TRADING_API_SECRET", "")
        self.dialogflow_url = "https://trading-dialogflow-webhook-cqlewkvzdq-uc.a.run.app/webhook"

    def query_alpaca_account(self, api_key: str, api_secret: str, account_type: str) -> dict | None:
        """
        Query Alpaca account.

        Args:
            api_key: Alpaca API key
            api_secret: Alpaca API secret
            account_type: "paper" or "brokerage"

        Returns:
            Account data dict or None if error
        """
        if not api_key or not api_secret:
            print(f"⚠️  {account_type.title()} credentials not found")
            return None

        base_url = "https://paper-api.alpaca.markets" if account_type == "paper" else "https://api.alpaca.markets"

        headers = {
            "accept": "application/json",
            "APCA-API-KEY-ID": api_key,
            "APCA-API-SECRET-KEY": api_secret
        }

        try:
            # Get account
            req = urllib.request.Request(f"{base_url}/v2/account", headers=headers)
            ssl_context = ssl.create_default_context()

            with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
                account = json.loads(response.read().decode("utf-8"))

            # Get positions
            req = urllib.request.Request(f"{base_url}/v2/positions", headers=headers)
            with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
                positions = json.loads(response.read().decode("utf-8"))

            # Calculate today's P/L
            equity = float(account["equity"])
            last_equity = float(account["last_equity"])
            daily_pl = equity - last_equity
            daily_pl_pct = (daily_pl / last_equity * 100) if last_equity > 0 else 0

            # Calculate total P/L from initial capital
            initial_capital = 5000 if account_type == "paper" else 20
            total_pl = equity - initial_capital
            total_pl_pct = (total_pl / initial_capital * 100)

            return {
                "equity": equity,
                "cash": float(account["cash"]),
                "last_equity": last_equity,
                "daily_pl": daily_pl,
                "daily_pl_pct": daily_pl_pct,
                "total_pl": total_pl,
                "total_pl_pct": total_pl_pct,
                "positions": len(positions),
                "position_details": positions,
                "status": account["status"],
                "account_type": account_type
            }

        except urllib.error.HTTPError as e:
            error_msg = e.read().decode("utf-8") if e.code != 403 else "Access denied (403)"
            print(f"❌ {account_type.title()} API Error {e.code}: {error_msg}")
            return None
        except Exception as e:
            print(f"❌ {account_type.title()} Error: {e}")
            return None

    def check_progress_dashboard(self) -> dict | None:
        """
        Check Progress Dashboard markdown file.

        Returns:
            Dashboard data dict or None if error
        """
        dashboard_path = project_root / "Progress-Dashboard.md"

        if not dashboard_path.exists():
            print("⚠️  Progress Dashboard not found")
            return None

        try:
            with open(dashboard_path, "r") as f:
                content = f.read()

            # Parse equity and P/L from markdown (simple regex-free parsing)
            lines = content.split("\n")
            paper_equity = None
            paper_total_pl = None
            paper_today_pl = None
            trades_today = None

            for i, line in enumerate(lines):
                if "PAPER" in line and "Equity" in lines[i+1] if i+1 < len(lines) else False:
                    # Found paper account section
                    for j in range(i, min(i+15, len(lines))):
                        if "**Equity**" in lines[j]:
                            paper_equity = lines[j].split("|")[2].strip().replace("$", "").replace(",", "")
                        elif "**Total P/L**" in lines[j]:
                            paper_total_pl = lines[j].split("|")[2].strip()
                        elif "**Today's P/L**" in lines[j]:
                            paper_today_pl = lines[j].split("|")[2].strip()
                        elif "**Trades Today**" in lines[j]:
                            trades_today = lines[j].split("|")[2].strip()

            return {
                "paper_equity": float(paper_equity) if paper_equity else None,
                "paper_total_pl": paper_total_pl,
                "paper_today_pl": paper_today_pl,
                "trades_today": trades_today
            }

        except Exception as e:
            print(f"❌ Dashboard parsing error: {e}")
            return None

    def query_dialogflow(self, question: str) -> str | None:
        """
        Query DialogFlow webhook.

        Args:
            question: Question to ask

        Returns:
            Response text or None if error
        """
        try:
            data = json.dumps({"text": question}).encode("utf-8")
            headers = {"Content-Type": "application/json"}

            req = urllib.request.Request(self.dialogflow_url, data=data, headers=headers, method="POST")
            ssl_context = ssl.create_default_context()

            with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
                result = json.loads(response.read().decode("utf-8"))
                return result["fulfillmentResponse"]["messages"][0]["text"]["text"][0]

        except Exception as e:
            print(f"❌ DialogFlow error: {e}")
            return None

    def generate_report(self) -> str:
        """
        Generate comprehensive session start report.

        Returns:
            Formatted report string
        """
        print("🔍 Querying data sources...\n")

        # Query Alpaca accounts
        paper_data = self.query_alpaca_account(self.paper_key, self.paper_secret, "paper")
        broker_data = self.query_alpaca_account(self.broker_key, self.broker_secret, "brokerage")

        # Check Progress Dashboard
        dashboard_data = self.check_progress_dashboard()

        # Query DialogFlow
        dialogflow_response = self.query_dialogflow("how much money did we make today?")

        # Generate report
        report = []
        report.append("═" * 70)
        report.append("📊 SESSION START REPORT")
        report.append("═" * 70)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %I:%M:%S %p ET')}")
        report.append(f"Source of Truth: Alpaca API")
        report.append("")

        # Paper Account Section
        report.append("─" * 70)
        report.append("💰 ALPACA PAPER $5K ACCOUNT (Source of Truth)")
        report.append("─" * 70)

        if paper_data:
            report.append(f"Equity:        ${paper_data['equity']:,.2f}")
            report.append(f"Cash:          ${paper_data['cash']:,.2f}")
            report.append(f"Today's P/L:   ${paper_data['daily_pl']:+,.2f} ({paper_data['daily_pl_pct']:+.2f}%)")
            report.append(f"Total P/L:     ${paper_data['total_pl']:+,.2f} ({paper_data['total_pl_pct']:+.2f}%)")
            report.append(f"Positions:     {paper_data['positions']}")
            report.append(f"Status:        {paper_data['status']}")

            if paper_data['positions'] > 0:
                report.append("")
                report.append("Open Positions:")
                for pos in paper_data['position_details']:
                    report.append(f"  • {pos['symbol']}: {pos['qty']} @ ${pos['current_price']} "
                                f"(P/L: ${pos['unrealized_pl']:+.2f})")
        else:
            report.append("❌ Could not access Alpaca Paper account")

        report.append("")

        # Brokerage Account Section
        report.append("─" * 70)
        report.append("💵 ALPACA BROKERAGE ACCOUNT (Source of Truth)")
        report.append("─" * 70)

        if broker_data:
            report.append(f"Equity:        ${broker_data['equity']:,.2f}")
            report.append(f"Cash:          ${broker_data['cash']:,.2f}")
            report.append(f"Today's P/L:   ${broker_data['daily_pl']:+,.2f} ({broker_data['daily_pl_pct']:+.2f}%)")
            report.append(f"Total P/L:     ${broker_data['total_pl']:+,.2f} ({broker_data['total_pl_pct']:+.2f}%)")
            report.append(f"Positions:     {broker_data['positions']}")
            report.append(f"Status:        {broker_data['status']}")
        else:
            report.append("❌ Could not access Alpaca Brokerage account")

        report.append("")

        # Verification Section
        report.append("─" * 70)
        report.append("✅ DATA VERIFICATION")
        report.append("─" * 70)

        # Check Progress Dashboard match
        if paper_data and dashboard_data:
            dashboard_equity = dashboard_data.get("paper_equity")
            if dashboard_equity:
                equity_match = abs(paper_data["equity"] - dashboard_equity) < 0.01
                report.append(f"Progress Dashboard Equity: ${dashboard_equity:,.2f} "
                            f"{'✅ MATCH' if equity_match else '❌ MISMATCH'}")
                if not equity_match:
                    report.append(f"  Difference: ${abs(paper_data['equity'] - dashboard_equity):,.2f}")
            else:
                report.append("Progress Dashboard: ⚠️  Could not parse equity")
        else:
            report.append("Progress Dashboard: ⚠️  No data to compare")

        # Check DialogFlow match
        if dialogflow_response:
            report.append(f"DialogFlow Response: {dialogflow_response}")
            # Simple check - if DialogFlow mentions today's P/L, verify it matches
            if paper_data and "$" in dialogflow_response:
                report.append("  ⚠️  Manual verification needed - compare values above")
        else:
            report.append("DialogFlow: ❌ No response")

        report.append("")

        # Today's Summary
        report.append("─" * 70)
        report.append("📅 TODAY'S SUMMARY")
        report.append("─" * 70)

        if paper_data:
            if paper_data["daily_pl"] > 0:
                report.append(f"✅ PROFIT: Made ${paper_data['daily_pl']:,.2f} today ({paper_data['daily_pl_pct']:+.2f}%)")
                report.append(f"Reason: Check open positions and recent trades above")
            elif paper_data["daily_pl"] < 0:
                report.append(f"❌ LOSS: Lost ${abs(paper_data['daily_pl']):,.2f} today ({paper_data['daily_pl_pct']:+.2f}%)")
                report.append(f"Reason: Check open positions and recent trades above")
            else:
                report.append(f"➖ FLAT: No change today (${paper_data['daily_pl']:,.2f})")
                report.append(f"Reason: No trades executed or market closed")
        else:
            report.append("❌ Cannot determine today's P/L (Alpaca API unavailable)")

        report.append("")
        report.append("═" * 70)

        return "\n".join(report)


def main():
    """Main entry point."""
    reporter = SessionStartReport()
    report = reporter.generate_report()
    print(report)

    # Save report to file
    report_path = project_root / "data" / "session_start_report.txt"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        f.write(report)
    print(f"\n📁 Report saved to: {report_path}")


if __name__ == "__main__":
    main()
