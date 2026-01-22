# EMERGENCY POSITION CLOSE

**Triggered**: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
**Reason**: Position imbalance crisis - 8 long vs 2 short
**Action**: Close 6 SPY260220P00658000 contracts

## Position Analysis
- SPY260220P00658000 (LONG): 8 contracts, -$1,248 loss
- SPY260220P00653000 (SHORT): 2 contracts, +$76 gain
- IMBALANCE: 6 extra long puts bleeding money

## Required Action
Close 6 contracts of SPY260220P00658000 to balance position

CLOSE_SYMBOL=SPY260220P00658000
CLOSE_QTY=6
CLOSE_SIDE=sell
