# Controlled Experiment Protocol (updated 2026-09-14 — AGENT-616 Buffett rebuild)

## Status — ACTIVE: spy_put_credit paper validation (Buffett v2 profile)

IC Simple remains **KILLED**. Live capital remains **blocked**.

## Rules

1. **Paper only.** No new live capital until kill criteria clear.
2. **Active family: spy_put_credit only.** Iron condor / ic_simple / 0DTE **new entries forbidden**.
3. **Profile: `spy-put-credit-buffett`** (default): 1-lot, $5 wide, ~15Δ short, **45–70 DTE** (target 60), **TP 50% / stop 200% / exit ~30 DTE**, **max 1 structure/day**, **max 1 concurrent**.
4. **SPY ≥ 200-DMA** required for new entries; VIX hard veto above 30.
5. **Max loss ≤ 1% of equity** per structure (Buffett Rule #1 budget).
6. **No same-expiry re-entry after a loss.**
7. **Minimum 24h hold** (except hard stop).
8. **One Buffett profile only** mid-cohort. No parameter drift.
9. **Gate on expectancy, not win rate:**
   - Pass only if realized expectancy > 0
   - Profit factor > 1.05
   - n ≥ 30 closed trades on **buffett** profile only
10. **Every trade auditable:** short delta, DTE, credit, hold time, exit reason, profile_name.
11. **Broker sync must be fresh** — if stale, no new entries.
12. **Open inventory must be clean** before new risk.
13. **Ignore "recover to $100K"** — process first, recovery second.

## Decision Gate

After 30 clean Buffett-profile put-credit closes:

- Edge → consider paper→live scale plan (still gated)
- No edge → kill put-credit and write a new hypothesis (do not revive IC)

## What NOT to do

- Resume iron condors or 0DTE "because win rate looks high"
- Add capital before edge is proven
- Count legacy TP-25% / 30-DTE closes toward the Buffett v2 gate
- Claim the strategy is profitable before n=30
