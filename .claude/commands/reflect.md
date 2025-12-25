# Reflect on Diary Entries

Analyze diary entries and feedback to generate rules for CLAUDE.md. This enables persistent learning across sessions.

## Instructions

### Step 1: Load Recent Diary Entries

Read all unprocessed diary entries from `~/.claude/memory/diary/`:

```bash
# Find entries not yet processed
PROCESSED=~/.claude/memory/diary/processed.log
touch $PROCESSED
find ~/.claude/memory/diary -name "*.md" -type f | while read f; do
  grep -q "$f" $PROCESSED || echo "$f"
done
```

### Step 2: Load Feedback Data

Read recent feedback from `data/feedback/`:
- `feedback_*.jsonl` files (last 7 days)
- `stats.json` for overall satisfaction rate

### Step 3: Analyze Patterns

Look for:
1. **Recurring mistakes** - Same error across multiple sessions
2. **User corrections** - Things user had to correct repeatedly
3. **Successful patterns** - What consistently worked well
4. **Explicit preferences** - Direct user statements about preferences

### Step 4: Generate Rules

Format rules as single-line, actionable directives:

**Good rule format:**
- `ALWAYS verify CI status before claiming PR is ready to merge`
- `NEVER claim a task is complete without showing evidence`
- `When user gives thumbs down, IMMEDIATELY ask what went wrong`

**Bad rule format:**
- `Be careful with CI` (too vague)
- `The user prefers when you show evidence because...` (too verbose)

### Step 5: Propose CLAUDE.md Updates

Present proposed additions to the user:

```markdown
## Proposed CLAUDE.md Additions

Based on analysis of [N] diary entries and [M] feedback items:

### New Rules from Session Learning
- [Rule 1]
- [Rule 2]
- [Rule 3]

### Patterns Detected
- [Pattern description]

Shall I add these to CLAUDE.md?
```

### Step 6: Update CLAUDE.md (with approval)

If user approves, add rules to the `## Session-Learned Rules` section of CLAUDE.md.

### Step 7: Mark Entries as Processed

```bash
echo "[processed_file_path]" >> ~/.claude/memory/diary/processed.log
```

## Example Output

```
Analyzed 3 diary entries and 5 feedback items.

Proposed CLAUDE.md Additions:

### New Rules from Session Learning
- ALWAYS show evidence (logs, commit hashes, screenshots) with every claim
- NEVER merge PRs without waiting for ALL CI checks to complete
- When fixing CI failures, check coverage thresholds not just test results

### Patterns Detected
- User values thoroughness over speed (3 occurrences)
- Negative feedback correlated with unverified claims (2 occurrences)

Add these rules to CLAUDE.md? (y/n)
```
