# LL-596 — Decisions UO: instructions are not control (2026-09-11)

**Source FORMAT:** Decisions _Who Governs the Machines?_ (Gartner universal orchestrator).
**Not a clone:** Decisions product, BOAT platform, or a ThumbGate UO SKU.

## Steal (3 tactics)

1. **Process state outside the agent** — journal / system_state / gate modules are the record, not chat memory.
2. **Rules before action** — `mandatory_trade_gate` is control; prompts are not.
3. **Observability: where / stuck / next** — every govern read answers those three; paper factory when occupancy < max; never live `--execute`.

## Rail

```bash
.venv/bin/python scripts/put_credit_govern.py
.venv/bin/python scripts/put_credit_govern.py --check-ready
.venv/bin/python -m pytest tests/test_put_credit_govern.py -q
```

## ThumbGate map (existing rails only)

| UO capability         | Already on ThumbGate                       |
| --------------------- | ------------------------------------------ |
| Runtime coordination  | PreToolUse / gates-engine                  |
| State outside agent   | session-lease, governance-state, lesson DB |
| Control before action | deny/warn gates (not prompt prose)         |
| where/stuck/next      | Issues dispositions + PR mergeStateStatus  |

Do **not** invent a ThumbGate "universal orchestrator" product (ECI pause on net-new governance SKUs).

Linear: AGENT-606
