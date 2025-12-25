# Session Diary Entry

Record what happened in this session for persistent learning across conversations.

## Instructions

Create a diary entry by analyzing the current session. Save it to `~/.claude/memory/diary/` with today's date and a sequence number.

### Diary Entry Format

```markdown
# Session Diary: [DATE] #[SEQUENCE]

## Session Summary
[1-2 sentence overview of what was accomplished]

## What Went Well
- [Specific things that worked, user was happy with]

## Mistakes Made
- [Specific errors, things user corrected, thumbs down moments]

## User Preferences Learned
- [Communication style, technical preferences, workflow habits]

## Rules to Remember
- [Synthesized rules from this session, formatted as actionable directives]

## Feedback Received
- [Any explicit thumbs up/down with context]
```

### Steps to Execute

1. Analyze the conversation history for:
   - Accomplishments and successful outcomes
   - Errors, corrections, or negative feedback
   - User preferences (explicit or implicit)
   - Patterns worth remembering

2. Create the diary file:
   ```bash
   DATE=$(date +%Y-%m-%d)
   SEQ=$(ls ~/.claude/memory/diary/${DATE}_*.md 2>/dev/null | wc -l)
   SEQ=$((SEQ + 1))
   FILE=~/.claude/memory/diary/${DATE}_session_${SEQ}.md
   ```

3. Write the entry to the file

4. Confirm to user: "Diary entry saved: [filename]"

### Example Output

```
Diary entry saved: ~/.claude/memory/diary/2025-12-25_session_1.md

Captured:
- What went well: CI fixes merged, all 22 checks passing
- Mistakes: Initially missed coverage threshold issue
- Preferences: User prefers evidence with every claim
- Rules: Always verify CI status before claiming success
```
