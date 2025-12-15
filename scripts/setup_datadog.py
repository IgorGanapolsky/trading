#!/usr/bin/env python3
"""
DATADOG MONITORING SETUP
========================
Sets up Datadog monitoring for trading operations.

Free tier includes:
- 5 hosts
- 1-day retention
- Real-time dashboards
- Alerts

Usage:
    # 1. Sign up at https://app.datadoghq.com/signup
    # 2. Get API key
    # 3. Set GitHub secret:
    gh secret set DD_API_KEY --body "your-api-key"

    # 4. Run this setup:
    python3 scripts/setup_datadog.py
"""

import os
from pathlib import Path


def create_datadog_integration():
    """Create Datadog integration script."""

    script_content = '''#!/usr/bin/env python3
"""
Send trading metrics to Datadog.

Usage:
    python3 scripts/report_to_datadog.py --trades 5 --profit 125.50 --status success
"""

import argparse
import os
import sys
import time
from datetime import datetime
import requests


def send_metrics_to_datadog(metrics: dict):
    """Send metrics to Datadog API."""
    api_key = os.environ.get('DD_API_KEY')
    if not api_key:
        print("⚠️  DD_API_KEY not set, skipping Datadog reporting")
        return

    url = "https://api.datadoghq.com/api/v1/series"
    headers = {
        "DD-API-KEY": api_key,
        "Content-Type": "application/json"
    }

    timestamp = int(time.time())

    series = []
    for metric_name, value in metrics.items():
        series.append({
            "metric": f"trading.{metric_name}",
            "points": [[timestamp, value]],
            "type": "gauge",
            "tags": [
                f"env:{'paper' if os.environ.get('ALPACA_PAPER') else 'live'}",
                "source:github_actions"
            ]
        })

    payload = {"series": series}

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        print(f"✅ Sent {len(metrics)} metrics to Datadog")
    except Exception as e:
        print(f"⚠️  Failed to send to Datadog: {e}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--trades', type=int, default=0)
    parser.add_argument('--profit', type=float, default=0.0)
    parser.add_argument('--status', type=str, default='unknown')
    parser.add_argument('--win-rate', type=float, default=0.0)
    args = parser.parse_args()

    metrics = {
        'trade_count': args.trades,
        'profit': args.profit,
        'status': 1 if args.status == 'success' else 0,
        'win_rate': args.win_rate,
    }

    print(f"📊 Trading Metrics:")
    print(f"  Trades: {args.trades}")
    print(f"  Profit: ${args.profit:+.2f}")
    print(f"  Status: {args.status}")
    print(f"  Win Rate: {args.win_rate:.1f}%")

    send_metrics_to_datadog(metrics)


if __name__ == "__main__":
    main()
'''

    output_file = Path(__file__).parent / "report_to_datadog.py"
    with open(output_file, 'w') as f:
        f.write(script_content)

    os.chmod(output_file, 0o755)
    print(f"✅ Created {output_file}")


def create_workflow_integration():
    """Show how to integrate with workflows."""

    integration_example = '''
# Add this to your trading workflows:

      - name: Report to Datadog
        if: always()
        env:
          DD_API_KEY: ${{ secrets.DD_API_KEY }}
        run: |
          python3 scripts/report_to_datadog.py \\
            --trades $TRADE_COUNT \\
            --profit $PROFIT \\
            --status ${{ job.status }} \\
            --win-rate $WIN_RATE
'''

    print("\n" + "=" * 60)
    print("WORKFLOW INTEGRATION")
    print("=" * 60)
    print(integration_example)


def main():
    """Set up Datadog monitoring."""
    print("🔧 DATADOG MONITORING SETUP")
    print("=" * 60)

    print("\n1. Sign up for Datadog (free tier):")
    print("   https://app.datadoghq.com/signup")

    print("\n2. Get your API key:")
    print("   https://app.datadoghq.com/organization-settings/api-keys")

    print("\n3. Set GitHub secret:")
    print("   gh secret set DD_API_KEY --body \"your-api-key\"")

    print("\n4. Creating integration script...")
    create_datadog_integration()

    print("\n5. Workflow integration example:")
    create_workflow_integration()

    print("\n" + "=" * 60)
    print("✅ DATADOG SETUP COMPLETE")
    print("\nNext steps:")
    print("  1. Sign up for Datadog")
    print("  2. Get API key")
    print("  3. Add to GitHub secrets")
    print("  4. Metrics will auto-report on next trading run")
    print("\nCost: $0 (free tier)")
    print("Benefits: Real-time visibility into trading operations")


if __name__ == "__main__":
    main()
