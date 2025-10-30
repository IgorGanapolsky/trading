#!/usr/bin/env python3
import alpaca_trade_api as tradeapi

api = tradeapi.REST(
    "PKSGVK5JNGYIFPTW53EAKCNBP5",
    "9DCF1pY2wgTTY3TBasjAHUWWLXiDTyrAhMJ4ZD6nVWaG",
    "https://paper-api.alpaca.markets",
)

account = api.get_account()
print(f"✅ Account Status: {account.status}")
print(f"💰 Buying Power: ${float(account.buying_power):,.2f}")
print(f"💵 Cash: ${float(account.cash):,.2f}")
print(f"📈 Equity: ${float(account.equity):,.2f}")
print(f'🔒 Paper Trading: {account.account_number.startswith("P")}')
