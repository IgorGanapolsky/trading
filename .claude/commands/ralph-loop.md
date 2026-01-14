# Ralph Loop - Autonomous Iteration Mode

Start an autonomous Ralph Wiggum loop that iterates on a task until completion.

## Usage
```
/ralph-loop "<your task prompt>" --max-iterations <n> --completion-promise "<text>"
```

## Arguments
- `prompt` (required): The task to iterate on
- `--max-iterations` (optional): Maximum iterations before stopping (default: 50)
- `--completion-promise` (optional): Text that signals completion (default: "COMPLETE")

## Instructions for Claude

When this command is invoked:

1. **Parse the arguments** from $ARGUMENTS:
   - Extract the main prompt (text in quotes or first argument)
   - Extract --max-iterations value (default: 50)
   - Extract --completion-promise value (default: "COMPLETE")

2. **Initialize Ralph state** by creating `.claude/ralph_state.json`:
```json
{
  "active": true,
  "iteration": 0,
  "max_iterations": <n>,
  "completion_promise": "<text>",
  "started_at": "<ISO timestamp>",
  "prompt": "<the prompt>"
}
```

3. **Save the prompt** to `.claude/ralph_prompt.txt`

4. **Begin execution** of the task:
   - Work on the prompt iteratively
   - After each major step, check if completion criteria are met
   - If outputting the completion promise, update state to `active: false`
   - The Stop hook will re-inject the prompt if you try to exit before completion

5. **Completion signals**:
   - Output `<promise>COMPLETE</promise>` (or custom promise) when done
   - Or reach max iterations
   - Or user runs `/cancel-ralph`

## Example

```bash
/ralph-loop "Fix all failing tests in the repo. Run pytest, fix each failure, repeat until all pass. Output <promise>COMPLETE</promise> when all tests green." --max-iterations 30
```

## Philosophy

- **Iteration > Perfection**: Don't aim for perfect on first try
- **Failures Are Data**: Use test failures to guide fixes
- **Persistence Wins**: Keep trying until success

## Safety

- Always set --max-iterations as a safety net
- Monitor API usage (loops burn tokens)
- Use `/cancel-ralph` to stop early
