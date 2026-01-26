# LL-313: RAG Hooks Audit - SessionEnd Hook Ineffective

**ID**: LL-313
**Date**: 2026-01-26
**Severity**: HIGH
**Category**: system-architecture, hooks
**Tags**: `rag`, `hooks`, `claude-code`, `session-end`, `stop-hook`

## Incident Summary

Audit of RAG hooks against official Claude Code documentation revealed that `capture_session_learnings.sh` is configured as a **SessionEnd** hook, which cannot inject context to Claude. This means lesson recording prompts are never seen by Claude.

## Root Cause

Per Claude Code hooks documentation:
- **SessionEnd**: "N/A, shows stderr to user only"
- **Stop**: "Blocks stoppage, shows stderr to Claude"

The `capture_session_learnings.sh` hook outputs to stdout, but SessionEnd hooks only show stderr to users - stdout goes nowhere useful. This is a fundamental misunderstanding of the hooks lifecycle.

## Impact

1. No automated lesson RECORDING mechanism exists
2. Lessons are only captured manually when Claude explicitly creates .md files
3. The learning loop is broken - we READ from RAG but don't systematically WRITE to it

## What's Working

| Hook | Event | Status |
|------|-------|--------|
| `advise_before_task.sh` | UserPromptSubmit | WORKING - reads JSON stdin, queries lessons |
| `mandatory_rag_check.sh` | UserPromptSubmit | WORKING - shows critical lessons (static) |
| `capture_session_learnings.sh` | SessionEnd | INEFFECTIVE - stdout ignored |

## Prevention Measures

1. **Use Stop hook instead of SessionEnd** for lesson capture prompts
   - Stop hooks CAN inject context and block stopping
   - Can use `"decision": "block"` to force continuation

2. **Consider prompt-based hooks** for intelligent evaluation:
   ```json
   {
     "type": "prompt",
     "prompt": "Evaluate if a lesson should be captured. Input: $ARGUMENTS"
   }
   ```

3. **Add PostToolUse hook** for automatic sync when writing to lessons_learned/

## Documentation Reference

Source: https://code.claude.com/docs/en/hooks

Key insight from docs:
```
| Hook Event    | Exit Code 2 Behavior                    |
|---------------|----------------------------------------|
| SessionEnd    | N/A, shows stderr to user only         |
| Stop          | Blocks stoppage, shows stderr to Claude |
```

## Related Lessons

- LL-306: CTO Ignores Surfaced RAG Lessons
- LL-227: RAG System Gap
