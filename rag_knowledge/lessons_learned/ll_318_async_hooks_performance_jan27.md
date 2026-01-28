# LL-318: Claude Code Async Hooks for Performance

**Date**: 2026-01-27
**Category**: Performance Optimization
**Source**: Boris Cherny (Claude Code team) - https://x.com/bcherny/status/2015524460481388760

## Problem
Session startup and prompt submission were slow due to many synchronous hooks running sequentially. Each hook blocked Claude's execution until completion.

## Solution
Add `"async": true` to hooks that are pure side-effects (logging, backups, notifications) and don't need to block execution.

```json
{
  "type": "command",
  "command": "./my-hook.sh",
  "async": true,
  "timeout": 30
}
```

## Which Hooks Should Be Async?

**YES - Make Async:**
- Backup scripts (backup_critical_state.sh)
- Feedback capture (capture_feedback.sh)
- Blog generators (auto_blog_generator.sh)
- Session learning capture (capture_session_learnings.sh)
- Any pure logging/notification hook

**NO - Keep Synchronous:**
- Hooks that provide context to Claude (inject_trading_context.sh)
- Hooks that must complete before next action (format_python.sh)
- Validation/protection hooks (protect_critical_files.sh)
- Hooks whose output Claude needs to see

## Impact
Reduced startup latency by ~15-20 seconds by making 5 hooks async.

## Key Insight
The difference between `&` at end of command (shell background) vs `"async": true`:
- Shell `&` detaches completely, may get killed
- `"async": true` runs in managed background, respects timeout, proper lifecycle

## Applied To
- capture_feedback.sh (UserPromptSubmit)
- backup_critical_state.sh (SessionStart)
- process_pending_feedback.sh (SessionStart)
- auto_blog_generator.sh (SessionStart)
- capture_session_learnings.sh (SessionEnd)
