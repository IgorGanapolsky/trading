# GPT-6 Astra harness FORMAT (InfoQ)

<!-- FORMAT steal from InfoQ "OpenAI Releases GPT-6 Astra…" (Sep 2026).
     Not OpenAI Codex / ChatGPT Pro / Astra API as primary. -->

**Source:** [InfoQ GPT-6 Astra](https://www.infoq.com/news/2026/09/openai-gpt6-astra/)

## Steal

| Astra idea                   | Our rail                                           |
| ---------------------------- | -------------------------------------------------- |
| Notes across context windows | `astra_session_notes.py` searchable JSONL          |
| Computer use                 | BrowserOS neo (existing)                           |
| Confirm consequential        | `astra_harness_gate` needs_confirm                 |
| Lower hallucination pressure | evidence-before-claim + ledgers                    |
| Critical cyber class         | offensive actions hard-fail                        |
| Expensive model              | **never** `gpt-6-astra` as primary under fleet cap |

## Automation

Integrated tick observe includes `astra_gate`. Agents persist durable facts via
session notes instead of relying on chat compaction alone.

## NEVER

- Default fleet brain to Astra API
- Claim 1M-context / OSWorld scores as ours
- Enable offensive cyber tooling
- Silent auto-send / live trade / force-push without confirm class
