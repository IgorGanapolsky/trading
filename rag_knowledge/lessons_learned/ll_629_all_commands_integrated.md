# LL-629 — All harness CLIs must be automated entrypoints

**Date:** 2026-09-15  
**Trigger:** CEO — all commands integrated/automated; never manual.

## Lesson

Scattered flags (`--ops-brief`, `--dup-health`, …) are agent internals. The human
surface is one integrated tick + LaunchAgent. Chat must not become a command menu.

## Prevention

`ralph_gsd_integrated_tick.py` + `make ralph-integrated` + LaunchAgent
`com.igor.trading.ralph-gsd-integrated` (30m). Scheduler/agents call that only.
