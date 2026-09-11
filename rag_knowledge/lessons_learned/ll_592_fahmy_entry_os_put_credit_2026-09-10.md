# LL-592: Fahmy episode OS → put-credit rails (not growth stocks)

**Date**: 2026-09-10
**Severity**: 3
**Category**: regime / entry process / FORMAT steal
**Source**: [Investing with IBD / Joe Fahmy](https://www.youtube.com/watch?v=YTqZtOMHZrk)

## What transferred

Episode rule: _Market healthy? Strong fundamentals? Clean technical? Predefined risk?_

Mapped onto **spy_put_credit** only:

1. **Market healthy** — existing IVR/VIX gate + new SPY **50-DMA** soft-flag beside 200-DMA.
2. **Structure strong** — defined-risk 1-lot bull put vertical with positive credit (not earnings acceleration screens).
3. **Clean technical** — short delta + DTE inside profile bands.
4. **Predefined risk** — stop, take-profit, time exit, and size must be written before entry.

Journaled on every plan as `entry_operating_system`. Entry blocked when any answer is no.

## What did NOT transfer

- Multi-name growth watchlists / ~30% YoY earnings screens
- Equity breakout entries
- Averaging down

Controlled experiment remains SPY put-credit paper validation.

## Evidence

- AGENT-602 / `src/risk/put_credit_regime.py` + `scripts/spy_put_credit.py`
- Tests in `tests/test_put_credit_regime.py`
