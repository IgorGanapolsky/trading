#!/usr/bin/env python3
"""
Bypass PDT to Close Positions

Strategy: Set pdt_check to "entry" (only check on opening, not closing)
Then attempt to close all option positions.

Based on Alpaca docs: pdt_check can be "both", "entry", or "exit"
Setting to "entry" should allow closing trades without PDT blocking.
"""

import os
import requests
import sys
from datetime import datetime

def main():
    print("=" * 60)
    print(f"PDT BYPASS CLOSE ATTEMPT - {datetime.now()}")
    print("=" * 60)

    api_key = os.environ.get('ALPACA_API_KEY') or os.environ.get('ALPACA_PAPER_TRADING_5K_API_KEY')
    api_secret = os.environ.get('ALPACA_SECRET_KEY') or os.environ.get('ALPACA_PAPER_TRADING_5K_API_SECRET')

    if not api_key or not api_secret:
        print("ERROR: No Alpaca credentials")
        sys.exit(1)

    base_url = "https://paper-api.alpaca.markets"
    headers = {
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": api_secret,
    }

    # Step 1: Get current config
    print("\n1️⃣ Getting current account config...")
    resp = requests.get(f"{base_url}/v2/account/configurations", headers=headers)
    if resp.status_code == 200:
        config = resp.json()
        print(f"   Current pdt_check: {config.get('pdt_check', 'unknown')}")
    else:
        print(f"   Failed to get config: {resp.status_code} - {resp.text}")

    # Step 2: Set pdt_check to "entry" (only block opening trades, not closing)
    print("\n2️⃣ Setting pdt_check to 'entry' (allow closing trades)...")
    resp = requests.patch(
        f"{base_url}/v2/account/configurations",
        headers=headers,
        json={"pdt_check": "entry"}
    )
    if resp.status_code == 200:
        print(f"   ✅ Config updated: {resp.json()}")
    else:
        print(f"   ⚠️ Config update response: {resp.status_code} - {resp.text}")

    # Step 3: Get positions
    print("\n3️⃣ Getting current positions...")
    resp = requests.get(f"{base_url}/v2/positions", headers=headers)
    if resp.status_code != 200:
        print(f"   Failed: {resp.text}")
        sys.exit(1)

    positions = resp.json()
    option_positions = [p for p in positions if len(p['symbol']) > 10]

    print(f"   Found {len(option_positions)} option positions:")
    for p in option_positions:
        print(f"   - {p['symbol']}: {p['qty']} @ ${float(p['unrealized_pl']):+.2f}")

    if not option_positions:
        print("\n✅ No option positions to close!")
        return

    # Step 4: Try to close ALL positions
    print("\n4️⃣ Attempting to close ALL option positions...")

    for pos in option_positions:
        symbol = pos['symbol']
        qty = abs(int(float(pos['qty'])))
        side = "sell" if float(pos['qty']) > 0 else "buy"

        print(f"\n   Closing {symbol} ({qty} contracts)...")

        # Method A: DELETE position endpoint
        print(f"      Method A: DELETE /positions/{symbol}...")
        resp = requests.delete(
            f"{base_url}/v2/positions/{symbol}",
            headers=headers
        )
        if resp.status_code in [200, 204]:
            print(f"      ✅ CLOSED via DELETE!")
            continue
        else:
            print(f"      ❌ DELETE failed: {resp.status_code} - {resp.text[:100]}")

        # Method B: Market order to close
        print(f"      Method B: Market order to {side}...")
        order_data = {
            "symbol": symbol,
            "qty": str(qty),
            "side": side,
            "type": "market",
            "time_in_force": "day"
        }
        resp = requests.post(
            f"{base_url}/v2/orders",
            headers=headers,
            json=order_data
        )
        if resp.status_code in [200, 201]:
            print(f"      ✅ Order submitted: {resp.json().get('id', 'unknown')}")
            continue
        else:
            print(f"      ❌ Order failed: {resp.status_code} - {resp.text[:100]}")

        # Method C: close_position with percentage
        print(f"      Method C: Close position request...")
        resp = requests.delete(
            f"{base_url}/v2/positions/{symbol}",
            headers=headers,
            params={"qty": str(qty)}
        )
        if resp.status_code in [200, 204]:
            print(f"      ✅ CLOSED via close_position!")
            continue
        else:
            print(f"      ❌ close_position failed: {resp.status_code} - {resp.text[:100]}")

    # Step 5: Verify
    print("\n5️⃣ Verifying remaining positions...")
    resp = requests.get(f"{base_url}/v2/positions", headers=headers)
    remaining = [p for p in resp.json() if len(p['symbol']) > 10]

    if remaining:
        print(f"\n⚠️ {len(remaining)} positions still open:")
        for p in remaining:
            print(f"   - {p['symbol']}: {p['qty']}")
    else:
        print("\n✅ ALL POSITIONS CLOSED!")

    # Step 6: Reset pdt_check to "both" for safety
    print("\n6️⃣ Resetting pdt_check to 'both' for safety...")
    requests.patch(
        f"{base_url}/v2/account/configurations",
        headers=headers,
        json={"pdt_check": "both"}
    )

    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)


if __name__ == "__main__":
    main()
