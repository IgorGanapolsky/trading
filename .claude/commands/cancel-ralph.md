# Cancel Ralph Loop

Stop an active Ralph Wiggum autonomous loop.

## Usage
```
/cancel-ralph
```

## Instructions for Claude

When this command is invoked:

1. **Check if Ralph mode is active** by reading `.claude/ralph_state.json`

2. **If active**, update the state:
```json
{
  "active": false,
  "ended_reason": "user_cancelled",
  "ended_at": "<ISO timestamp>"
}
```

3. **Report status**:
   - How many iterations completed
   - What was accomplished
   - Any remaining work

4. **Clean exit** - normal operation resumes

## Example Output

```
🛑 Ralph Loop Cancelled

Completed: 12/50 iterations
Duration: 15 minutes
Progress:
- Fixed 8 of 15 test failures
- Remaining: 7 tests still failing

To resume: /ralph-loop "Continue fixing tests..." --max-iterations 20
```
