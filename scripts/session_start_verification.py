#!/usr/bin/env python3
"""
Session Start Verification Script

Runs at the start of every Claude session to verify data consistency across:
1. Alpaca API (source of truth)
2. system_state.json (local cache)
3. GitHub Pages dashboard
4. Dialogflow (if configured)

CEO Directive (Jan 15, 2026):
"Every time I start a session, report exactly how much money we made today or lost today,
verify dashboard matches Alpaca (source of truth), and query Dialogflow to verify."
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def fetch_alpaca_data():
    """Fetch live data from Alpaca API (source of truth)."""
    try:
        from src.utils.alpaca_client import get_alpaca_credentials
        import requests

        api_key, secret_key = get_alpaca_credentials()
        if not api_key or not secret_key:
            return None, "No Alpaca credentials available"

        headers = {
            'APCA-API-KEY-ID': api_key,
            'APCA-API-SECRET-KEY': secret_key
        }

        # Fetch account
        resp = requests.get(
            'https://paper-api.alpaca.markets/v2/account',
            headers=headers,
            timeout=10
        )
        if resp.status_code != 200:
            return None, f"Alpaca API error: {resp.status_code}"

        account = resp.json()

        # Fetch positions
        pos_resp = requests.get(
            'https://paper-api.alpaca.markets/v2/positions',
            headers=headers,
            timeout=10
        )
        positions = pos_resp.json() if pos_resp.status_code == 200 else []

        equity = float(account['equity'])
        last_equity = float(account['last_equity'])
        today_pl = equity - last_equity
        total_pl = equity - 5000.0  # From initial $5K

        return {
            'source': 'ALPACA_API',
            'equity': equity,
            'cash': float(account['cash']),
            'today_pl': today_pl,
            'total_pl': total_pl,
            'total_pl_pct': (total_pl / 5000.0) * 100,
            'positions_count': len(positions),
            'positions': positions,
            'timestamp': datetime.now().isoformat()
        }, None

    except ImportError:
        return None, "Missing dependencies (requests)"
    except Exception as e:
        return None, f"Error: {str(e)}"


def fetch_local_cache():
    """Fetch data from local system_state.json."""
    state_file = Path(__file__).parent.parent / 'data' / 'system_state.json'
    if not state_file.exists():
        return None, "system_state.json not found"

    try:
        data = json.loads(state_file.read_text())
        return {
            'source': 'LOCAL_CACHE',
            'equity': data.get('paper_account', {}).get('equity', 0),
            'cash': data.get('paper_account', {}).get('cash', 0),
            'today_pl': data.get('paper_account', {}).get('daily_change', 0),
            'total_pl': data.get('paper_account', {}).get('total_pl', 0),
            'total_pl_pct': data.get('paper_account', {}).get('total_pl_pct', 0),
            'positions_count': data.get('paper_account', {}).get('positions_count', 0),
            'timestamp': data.get('last_updated', 'unknown')
        }, None
    except Exception as e:
        return None, f"Error reading cache: {str(e)}"


def fetch_github_pages():
    """Fetch data from GitHub Pages dashboard."""
    try:
        import requests
        resp = requests.get(
            'https://igorganapolsky.github.io/trading/data/dashboard.json',
            timeout=10
        )
        if resp.status_code != 200:
            return None, f"GitHub Pages error: {resp.status_code}"

        data = resp.json()
        return {
            'source': 'GITHUB_PAGES',
            'equity': data.get('equity', 0),
            'total_pl': data.get('total_pl', 0),
            'total_pl_pct': data.get('total_pl_pct', 0),
            'timestamp': data.get('last_updated', 'unknown')
        }, None
    except Exception as e:
        return None, f"Error: {str(e)}"


def query_dialogflow():
    """Query Dialogflow for portfolio status."""
    try:
        project_id = os.environ.get('DIALOGFLOW_PROJECT_ID', 'ai-trading-agent-igor')

        # Try using Google API key for simple query
        google_api_key = os.environ.get('GOOGLE_API_KEY')
        if not google_api_key:
            return None, "No GOOGLE_API_KEY available"

        import requests

        # Dialogflow REST API endpoint
        url = f"https://dialogflow.googleapis.com/v2/projects/{project_id}/agent/sessions/session-verify:detectIntent"

        headers = {
            'Authorization': f'Bearer {google_api_key}',
            'Content-Type': 'application/json'
        }

        payload = {
            'queryInput': {
                'text': {
                    'text': 'How much money did we make today?',
                    'languageCode': 'en'
                }
            }
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        if resp.status_code != 200:
            return None, f"Dialogflow error: {resp.status_code}"

        data = resp.json()
        fulfillment = data.get('queryResult', {}).get('fulfillmentText', 'No response')

        return {
            'source': 'DIALOGFLOW',
            'response': fulfillment,
            'timestamp': datetime.now().isoformat()
        }, None

    except Exception as e:
        return None, f"Error: {str(e)}"


def compare_sources(alpaca, cache, pages):
    """Compare data sources and identify discrepancies."""
    discrepancies = []

    if alpaca and cache:
        equity_diff = abs(alpaca['equity'] - cache['equity'])
        if equity_diff > 1.0:  # $1 tolerance
            discrepancies.append(f"Equity mismatch: Alpaca=${alpaca['equity']:.2f} vs Cache=${cache['equity']:.2f}")

        pos_diff = abs(alpaca['positions_count'] - cache['positions_count'])
        if pos_diff > 0:
            discrepancies.append(f"Position count mismatch: Alpaca={alpaca['positions_count']} vs Cache={cache['positions_count']}")

    if alpaca and pages:
        equity_diff = abs(alpaca['equity'] - pages.get('equity', 0))
        if equity_diff > 1.0:
            discrepancies.append(f"Equity mismatch: Alpaca=${alpaca['equity']:.2f} vs Pages=${pages.get('equity', 0):.2f}")

    return discrepancies


def main():
    """Main verification routine."""
    print("=" * 60)
    print("SESSION START VERIFICATION")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S ET')}")
    print("=" * 60)

    # Fetch from all sources
    alpaca_data, alpaca_err = fetch_alpaca_data()
    cache_data, cache_err = fetch_local_cache()
    pages_data, pages_err = fetch_github_pages()
    dialogflow_data, dialogflow_err = query_dialogflow()

    # Report Alpaca (Source of Truth)
    print("\n📊 ALPACA (SOURCE OF TRUTH)")
    if alpaca_data:
        print(f"  Equity: ${alpaca_data['equity']:,.2f}")
        print(f"  Cash: ${alpaca_data['cash']:,.2f}")
        print(f"  Today's P/L: ${alpaca_data['today_pl']:+,.2f}")
        print(f"  Total P/L: ${alpaca_data['total_pl']:+,.2f} ({alpaca_data['total_pl_pct']:+.2f}%)")
        print(f"  Positions: {alpaca_data['positions_count']}")
    else:
        print(f"  ❌ {alpaca_err}")

    # Report Local Cache
    print("\n📁 LOCAL CACHE (system_state.json)")
    if cache_data:
        print(f"  Equity: ${cache_data['equity']:,.2f}")
        print(f"  Today's P/L: ${cache_data['today_pl']:+,.2f}")
        print(f"  Total P/L: ${cache_data['total_pl']:+,.2f} ({cache_data['total_pl_pct']:+.2f}%)")
        print(f"  Positions: {cache_data['positions_count']}")
        print(f"  Last Updated: {cache_data['timestamp']}")
    else:
        print(f"  ❌ {cache_err}")

    # Report GitHub Pages
    print("\n🌐 GITHUB PAGES")
    if pages_data:
        print(f"  Equity: ${pages_data.get('equity', 0):,.2f}")
        print(f"  Total P/L: ${pages_data.get('total_pl', 0):+,.2f}")
    else:
        print(f"  ❌ {pages_err}")

    # Report Dialogflow
    print("\n🤖 DIALOGFLOW")
    if dialogflow_data:
        print(f"  Response: {dialogflow_data['response']}")
    else:
        print(f"  ❌ {dialogflow_err}")

    # Compare and report discrepancies
    discrepancies = compare_sources(alpaca_data, cache_data, pages_data)

    print("\n" + "=" * 60)
    if discrepancies:
        print("🚨 DISCREPANCIES DETECTED:")
        for d in discrepancies:
            print(f"  ⚠️  {d}")
        print("\nAction: Run 'gh workflow run sync-alpaca-status.yml' to sync")
    else:
        print("✅ All sources consistent (within tolerance)")
    print("=" * 60)

    # Return summary for hook consumption
    return {
        'alpaca': alpaca_data,
        'cache': cache_data,
        'pages': pages_data,
        'dialogflow': dialogflow_data,
        'discrepancies': discrepancies,
        'verified_at': datetime.now().isoformat()
    }


if __name__ == '__main__':
    main()
