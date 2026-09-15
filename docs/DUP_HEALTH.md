# Duplication / refactor health (TNS FORMAT)

<!-- FORMAT steal from The New Stack / GitClear Maintainability Gap (Steve Fenton,
     Sep 2026). Not a GitClear product clone. -->

**Source:** [Your AI coding spend bought 25% more output. Duplication rose 81%.](https://thenewstack.io/ai-coding-duplication-rose/)

## Steal

| Signal                | Industry (GitClear)               | Our rail                                     |
| --------------------- | --------------------------------- | -------------------------------------------- |
| Output velocity       | +25% for heavy AI users (not 10x) | Do not equate LOC/PR count with fee-yes      |
| Block duplication     | +81% (40.3 → 73.0 / MLOC)         | `scripts/dup_health.py` `blocks_per_million` |
| Moved code (refactor) | 21% → 3.8% of changed lines       | `--git-range` moved/copy file ratio          |
| Practices             | Tests + refactor are the mission  | Prefer extract/move over copy-paste          |

## Commands

```bash
python3 scripts/dup_health.py --path scripts --path src
python3 scripts/dup_health.py --git-range HEAD~30..HEAD --strict
python3 scripts/ralph_gsd_tick.py --dup-health --path scripts
```

## Fail-closed doctrine

- AI velocity pressure without maintainability gates → whack-a-mole bugs.
- Claiming “productivity” from PR volume while duplication rises is theater.
- Do not install GitClear SaaS for this lab — local CLI is enough.

## Related

InfoQ SDD attribution (`docs/SPEC_GOVERNANCE.md`) catches intent drift; this catches
**copy-paste sprawl**. Both are verification-side investments.
