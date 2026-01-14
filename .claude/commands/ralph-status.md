# Ralph Status

Check the status of an active or recent Ralph Wiggum loop.

## Usage
```
/ralph-status
```

## Instructions for Claude

When this command is invoked:

1. **Read Ralph state** from `.claude/ralph_state.json`

2. **Display status**:
   - Active or inactive
   - Current iteration / max iterations
   - Time running
   - Original prompt
   - Completion promise being watched for

3. **If no state file exists**, report that no Ralph loop has been started

## Example Output (Active)

```
🔄 Ralph Loop Status: ACTIVE

Iteration: 8/50
Running for: 12 minutes
Started: 2026-01-14 16:15:00

Prompt: "Fix all failing tests..."
Completion Promise: "COMPLETE"

To cancel: /cancel-ralph
```

## Example Output (Inactive)

```
💤 Ralph Loop Status: INACTIVE

Last run: 2026-01-14 15:30:00
Completed: 25 iterations
Ended: max_iterations reached

To start: /ralph-loop "<prompt>" --max-iterations 50
```
