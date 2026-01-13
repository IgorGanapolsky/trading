# Trade Trigger - STOP LOSS ORDER

**Triggered:** 2026-01-13T15:12:00Z
**Action:** SET STOP-LOSS ON PUT
**Symbol:** SOFI260206P00024000
**Order:** BUY TO CLOSE @ $1.50 LIMIT (GTC)

## Risk Management

CEO Directive: "We are never allowed to lose money!"

Setting protective stop-loss on existing short put position:
- Current put price: ~$0.80
- Stop-loss trigger: $1.50
- Max loss if triggered: $150 - $79 premium = $71 net loss
- Without stop-loss: Unlimited downside risk

## Order Details

```python
# Buy to close the short put if it reaches $1.50
order = {
    "symbol": "SOFI260206P00024000",
    "qty": 1,
    "side": "buy",  # Buy to close short position
    "type": "stop_limit",
    "stop_price": 1.50,
    "limit_price": 1.55,
    "time_in_force": "gtc"  # Good till canceled
}
```

## Expected Outcome

1. Stop-loss order placed on existing put position
2. If SOFI drops and put rises to $1.50, order triggers
3. Max loss capped at ~$71 instead of unlimited
