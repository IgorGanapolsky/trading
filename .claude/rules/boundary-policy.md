# Boundary Policy

This document codifies the boundary-crossing rules enforced by `.claude/hooks/`.
It is the machine-readable companion to `risk-management.md` and `trading.md`.
A Codex-style auto-reviewer (or any future PreToolUse guard)
should treat the **Hard Blocks** below as policy-deny decisions.

## Hard Blocks (deny without explicit override)

1. **Closing positions outside the reconciled manager workflow.**
   Bash: any command matching `close_position`, `liquidat`, or
   `submit_order.*SELL`. MCP: any `mcp__alpaca__close_position`,
   `close_all_positions`, `cancel_order`, `cancel_all_orders`, `liquidate`.
   Owner: `.github/workflows/put-credit-validation.yml`, which invokes
   `scripts/spy_put_credit.py --manage-exits` and `scripts/residual_ic_manager.py`.
   Lessons: LL-306, LL-325.

2. **Removing the TRADING_HALTED kill-switch.**
   Bash: `rm`/`mv`/`>` against `data/TRADING_HALTED`, `data/SYSTEM_HALTED`,
   or `data/trading_halt.txt`. Edit/Write/NotebookEdit on the same paths.
   The file is read by `src/risk/trade_gateway.py`; deleting it re-enables
   trade execution. Auto-clear is reserved for `src/safety/crisis_monitor.py`
   when open option positions == 0.

3. **Modifying canonical risk constants without explicit override.**
   Edit/Write on `src/core/trading_constants.py` that touches
   `IRON_CONDOR_STOP_LOSS_MULTIPLIER`, `MAX_CONCURRENT_IRON_CONDORS`,
   `NORTH_STAR_MONTHLY_AFTER_TAX`, or `FORBIDDEN_STRATEGIES`. These are
   pinned by `.claude/CLAUDE.md` (`Canonical Policy Constants`).

4. **Hardcoding credentials.** Any new occurrence of `APCA_API_KEY_ID=`,
   `APCA_API_SECRET_KEY=`, or similar literals in source. GitGuardian
   incident, Feb 3 2026. All credential reads must go through
   `get_alpaca_credentials()` in `src/utils/alpaca_client.py`.

5. **Force-push to `main`.** `git push --force`, `git push -f`, or
   any history-rewriting push targeting `origin/main`.

## Soft Gates (warn but allow)

1. **Stale system state.** If `data/system_state.json` mtime is > 24h,
   warn before any tool call that reaches Alpaca. Code-level enforcement
   lives in `src/utils/staleness_guard.py`.

2. **Public-surface edits.** Edits under `docs/`, `wiki/`, `blog/` are
   outside the active operating scope per `CLAUDE.md` (Simplification
   Mandate). Allowed but flagged.

## Override

One-shot override file: `/tmp/claude_magic_word_authorized`.
Create it, perform the single action, the hook consumes (deletes) the file.
Mirrors the magic-word convention in `require_magic_word.sh`.

## Enforcement matrix

| Tool surface                              | Hook script                                        |
| ----------------------------------------- | -------------------------------------------------- |
| `Bash`                                    | `block_position_close.sh`, `require_magic_word.sh` |
| `Edit`/`Write`/`MultiEdit`/`NotebookEdit` | `guard_destructive_actions.sh`                     |
| `mcp__alpaca__*`                          | `guard_destructive_actions.sh`                     |

Wiring lives in `.claude/settings.json` under `hooks.PreToolUse`.

## Circuit breaker

Not yet implemented as a hook. The closest in-code analog is
`src/utils/api_circuit_breaker.py` (broker-side). If repeated boundary
denials are observed in `.claude/logs/gsd-hook-pipeline.log`, the
operator should halt the session manually until the root cause is
addressed — the policy is "denials are signal, not friction."
