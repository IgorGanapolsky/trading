# LL-628 — Thumbs down: command blocks in chat are still homework

**Date:** 2026-09-15  
**Signal:** thumbs down (severity 4)  
**Context:** After CEO said "i never run commands manually. save that directive forever", agent still surfaced "Commands" fences / `ralph --…` as if for the user.

## Correction

- Never paste runnable command blocks for Igor in chat — even labeled "documentation" or "evidence how to invoke".
- Agent runs the CLI itself and reports outcomes (exit, SHA, counts).
- Do not restate the zero-manual rule every turn (silent HARD like always-agent-mode).
- Skill `/zero-manual-handoff` already owns this; obey silently.

## Prevention

- Before any user-facing "```bash" block: if Igor would be the one to type it → delete and execute instead.
- Docs in-repo may keep CLI examples; chat replies must not.
