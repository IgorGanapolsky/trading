# Capture Session Learning

Capture a significant insight from this session to the lessons learned knowledge base.

## Instructions

1. First, run the capture hook to get the next lesson number:
```bash
$CLAUDE_PROJECT_DIR/.claude/hooks/capture_session_learnings.sh
```

2. Identify the key learning from this session. Ask yourself:
   - What bug/error/gotcha was discovered?
   - What's the root cause?
   - How can this be prevented in the future?

3. Create the lesson file with format:
   - Filename: `rag_knowledge/lessons_learned/ll_[NUM]_[topic]_[month][day].md`
   - Example: `ll_035_magic_docs_pattern_dec15.md`

4. Use this template:

```markdown
# Lesson Learned: [Title]

**ID**: LL_[NUM]
**Date**: [YYYY-MM-DD]
**Severity**: [LOW|MEDIUM|HIGH|CRITICAL]
**Category**: [Architecture|Bug|Configuration|Process|Security|Trading]
**Tags**: [comma, separated, tags]

## Incident Summary

[1-2 sentences: What happened?]

## Root Cause

[Why did this happen? Be specific.]

## Impact

[What was the consequence? Quantify if possible.]

## Prevention Measures

[Concrete steps to prevent recurrence]

## Detection Method

[How was this discovered?]

## Related Lessons

[Link to related LL_XXX if any]
```

5. Only capture if the learning is:
   - Non-obvious (not readable from code)
   - Likely to recur without documentation
   - Valuable for future sessions

**Do NOT capture**: Trivial fixes, temporary workarounds, or session-specific context.
