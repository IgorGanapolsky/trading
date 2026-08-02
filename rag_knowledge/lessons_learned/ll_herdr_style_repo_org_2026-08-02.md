# LL — Herdr-style repo organization (2026-08-02)

## Context

CEO asked to steal high-ROI ideas from Herdr’s public repo and docs
([herdrdev/herdr](https://github.com/herdrdev/herdr), agent-skill + plugins docs).

## What we copied (adapted)

1. **Clean README pitch** — short value prop, quick start, docs links, honest non-claim
2. **First-class agent skill** — `skills/trading-ops/SKILL.md` (operate vs teach split)
3. **Docs hub** — `docs/README.md` + `docs/operator-guide.md`
4. **CONTRIBUTING.md** — PR path for humans/agents
5. **AGENTS.md pointer** — skill + contributing at top
6. **make check** — fast lint + layout tests

## What we did not copy

- Plugin marketplace / herdr-plugin.toml (not applicable to trading lab yet)
- Multi-channel release docs pipeline

## Rule

Public README must not claim proven edge. Point to ledgers. Credit Herdr as inspiration without affiliation.

## Tags

#docs #skill #repo-org #herdr-inspired
