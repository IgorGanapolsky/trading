# Win Rate Diagnosis: 37.5% vs 80%+ Target (Feb 8, 2026)

## Source: System state analysis + OptionsTradingIQ + Option Alpha

### The Problem
system_state.json shows 37.5% win rate across all trades.
Target is 80%+ for iron condors.
This gap MUST be investigated before scaling.

### Likely Causes (from research)
1. **Mixed trade types** — 95 total trades include stock purchases (VICI, DLR, AMT), not just iron condors. Win rate is polluted by non-condor trades.
2. **No 50% profit auto-close running** — code exists but isn't scheduled. Positions held too long, turning winners into losers.
3. **No adjustment logic** — when a side is tested, system doesn't roll the untested side closer. Research shows adjustments boost win rate by 16 percentage points (70% → 86%).
4. **Possible wrong delta/DTE** — need to verify actual executed trades matched 15-delta, 30-45 DTE parameters.

### Action Required
1. **Decompose win rate by trade type** — separate iron condor P/L from stock P/L
2. **Implement scheduled position monitoring** — auto-close at 50% profit
3. **Add adjustment logic** — roll untested side when tested side is challenged
4. **Audit the 7 completed iron condors** — what delta/DTE were they actually at?

### Research Findings on Fixing Low Win Rate
- Close at 50% profit → boosts win rate from 70% to 85%+ (OptionsTradingIQ)
- Roll unchallenged side closer when tested → reduces max loss, adds credit
- Enter only when IV rank > 50 (ideally > 70) → better premium, wider range
- Manage mechanically, not emotionally → code handles this

### Priority
CRITICAL — cannot scale to Phase 2 until iron condor win rate is proven at 80%+
