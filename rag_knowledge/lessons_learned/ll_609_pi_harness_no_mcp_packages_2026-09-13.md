# LL-609 Pi harness: skills/CLI, not third-party MCP packages

## Context

2026-09-13. Capitalize on [pi.dev](https://pi.dev/) for the trading lab. Pi's own philosophy is **no MCP in core** — skills, prompt templates, SYSTEM append, and a permission-gate **extension**. PR #4624 already owns `/status` prompts + `pi_trading_bridge.py`. This slice adds SYSTEM/settings/live-gate/factory skill without dual-editing that PR.

Installing unreviewed `pi install npm:…-mcp` packages runs arbitrary code (Pi package security note). Grok/Claude already have Linear/GitHub MCP.

## Prevention

- `.pi/settings.json` `packages: []` and `enableInstallTelemetry: false`
- `.pi/extensions/trading-live-gate.ts` blocks live/close/halt-delete
- Tests in `tests/test_pi_harness.py`

## Do not

- Dual-edit #4624 files
- Flip `live_blocked`
- Treat Pi print-mode as a trade
