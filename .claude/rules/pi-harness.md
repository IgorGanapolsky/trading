# Pi harness (pi.dev) — trading lab

Pi is a minimal agent harness. This repo uses Pi **FORMAT** (prompts, skills, SYSTEM append, permission-gate extension). It does **not** replace Grok/Claude and does **not** add MCP to Pi.

## Do

- Load `.pi/APPEND_SYSTEM.md`, `.pi/skills/pi-paper-factory/`, `.pi/extensions/trading-live-gate.ts`
- Call existing Python CLIs for status / dry-run / scorecard
- Keep `live_blocked` until EDGE_CANDIDATE

## Do not

- Dual-edit PR #4624 files (`.pi/prompts/{status,dryrun,exits,scorecard,hygiene}.md`, `scripts/pi_trading_bridge.py`, Makefile `pi-*`)
- `pi install` unreviewed npm MCP adapters (`pi-mcp-adapter`, `@eliemessiecode/pi-mcp`, etc.)
- Clone Pi as a product SKU or bake MCP into core
- Use Pi print-mode paid models to invent trades the scripts already plan
