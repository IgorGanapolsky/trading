# Risk Management Rules

## Canonical Policy Constants

- IRON_CONDOR_STOP_LOSS_MULTIPLIER: 2.0 (CEO-approved 2026-07-02, validation cohort; was 1.0)
- NORTH_STAR_MONTHLY_AFTER_TAX: 6000
- MAX_POSITIONS: 8

## Phil Town Rule #1: Don't Lose Money

### Position Sizing

- NEVER more than 5% on single trade ($5,000 risk per position)
- 2 put-credit structures max concurrent; residual IC inventory is exit-only
- NO NAKED OPTIONS, NO UNDEFINED RISK

### Stop-Loss (MANDATORY)

- Close if total loss reaches 200% of credit (CEO-approved 2026-07-02; was 100%) — NO EXCEPTIONS
- Do not add risk to repair a tested structure
- Exit at 7 DTE to avoid gamma risk (changed from 21 DTE per LL-268)

### Exit Rules

- Close at 25% max profit OR 7 DTE (whichever first; CEO-approved 2026-07-02, was 50%)
- PDT NOTE: $100K > $25K = no PDT restrictions

### Financial Independence Path

- Scaling is blocked until the active paper cohort has at least 30 paired closes,
  positive expectancy, and profit factor above 1.
- Capital deployment and withdrawal claims require provider-visible evidence.

### Tax Optimization

- SPY = equity options = 100% short-term capital gains
- XSP/SPX = Section 1256 = 60/40 tax treatment, no wash sales
- Set aside 30% quarterly for estimated taxes
- File Form 6781 for Section 1256 contracts
