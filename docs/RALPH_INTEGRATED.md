# Ralph integrated tick (zero manual)

CEO 2026-09-15: all harness commands are integrated and automated. Humans do not
run CLI homework.

## Entrypoint

`scripts/ralph_gsd_integrated_tick.py` (also `ralph_gsd_tick.py --integrated`)

Each fire automatically runs:

1. Ops daily brief (recommend-only alerts + provenance)
2. Eval-first ledger summary
3. Fan-out memory budget
4. HydraFusion route for the picked residual
5. Default pick + phase loop + STATE/CONTEXT

## Automation surfaces

| Surface        | Wiring                                                          |
| -------------- | --------------------------------------------------------------- |
| Make           | `make ralph-integrated`                                         |
| LaunchAgent    | `com.igor.trading.ralph-gsd-integrated` (30m)                   |
| Grok scheduler | `/trading-ralph-gsd-24-7` fires this entrypoint                 |
| DAIR daily     | harvest → implement; trading integrated is separate LaunchAgent |

## NEVER

Paste CLI blocks for Igor. The agent or LaunchAgent runs the entrypoint and
reports outcomes (JSON path, residual, recommends).

Committed template: `scripts/launchd/com.igor.trading.ralph-gsd-integrated.plist.example` (no machine `/Users` paths).
