# Put-credit protocol selection rule (fixed)

A challenger protocol replaces the incumbent champion only if ALL of the following hold
on the **validation** slice of closed put-credit trades (not development, not holdout):

1. Validation expectancy is not worse than the incumbent's
2. Validation profit factor is not worse than the incumbent's (when both defined)
3. Validation total realized P/L is not worse than the incumbent's
4. Challenger has at least as many closed trades as the incumbent on the validation slice

Ties go to the incumbent. Higher development expectancy alone is never sufficient.
Holdout metrics are never used until a champion is frozen.
