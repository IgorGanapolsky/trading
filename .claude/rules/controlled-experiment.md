# Controlled Experiment Protocol (updated 2026-07-22)

## Status — ACTIVE: spy_put_credit paper validation (IC Simple KILLED)

## Rules

1. **Paper only.** No new live capital. No Clear Street / venue migration until edge proven.
2. **Active family: spy_put_credit only.** Iron condor / ic_simple **new entries forbidden**.
3. **Max 3 structures per day** (profile `max_daily_structures=3`, landed #4274). 1-lot only. Max 2 concurrent put credits.
4. **No same-expiry re-entry after a loss.**
5. **Minimum 24h hold** (except hard stop).
6. **One profile only** (`spy-put-credit`). No parameter drift mid-cohort.
7. **Gate on expectancy, not just win rate:**
   - Pass only if realized expectancy > 0
   - Profit factor > 1
   - Win rate above realized break-even level
8. **Every trade auditable:** short delta, DTE, credit, hold time, exit reason.
9. **Broker sync must be fresh** — if stale, no new entries.
10. **Open inventory must be clean** before new risk (no orphan legs / lot mismatches).
11. **Ignore "recover to $100K"** — process first, recovery second.

## Decision Gate

After 30 clean put-credit setups:

- System has edge → consider scale (still paper→live gate)
- System has no edge → kill put-credit and redesign again (do not revive IC by default)

## What NOT to do

- Resume iron condors "because last 4 were winners"
- Add capital before edge is proven
- Switch to live or Clear Street mid-validation
- Optimize only for "80% win rate" headline
- Claim the strategy is profitable before n=30
