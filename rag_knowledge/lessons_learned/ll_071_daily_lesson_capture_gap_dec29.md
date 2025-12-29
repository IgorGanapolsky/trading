# Lesson Learned: Daily Lesson Capture Was Not Enforced

**ID**: LL_071
**Date**: December 29, 2025
**Severity**: HIGH
**Category**: Process, Documentation, Knowledge Management
**Tags**: lessons-learned, rag, automation, process-gap

## Incident Summary

Despite having 70+ documented lessons and a comprehensive lessons capture system, lessons were NOT being recorded daily. The last lesson (LL_070) was from December 24, 2025 - creating a 5-day gap.

The GitHub Pages site at igorganapolsky.github.io/trading/lessons/ claims "New lessons are added automatically when we learn from failures" - but this was not happening.

## Root Cause

1. **Hook only suggests, doesn't enforce**: The `capture_session_learnings.sh` hook outputs a template and directions but doesn't actually create lessons
2. **No session-end requirement**: Nothing enforced capturing learnings before ending a session
3. **Passive system**: Relied on Claude voluntarily remembering to capture lessons
4. **docs/_lessons/ not local**: The Jekyll collection only exists in CI, so local verification was impossible

## Impact

- Lost 5 days of potential learning documentation
- GitHub Pages site became stale
- RAG knowledge base missing recent insights
- Broke the "continuous learning" promise to stakeholders

## Prevention Measures

1. **Add to SESSION_START_CHECKLIST.md**: Mandatory review of whether yesterday's lessons were captured
2. **Session-end enforcement**: Before ending any session, check if a lesson was recorded today
3. **Daily verification in hooks**: Add a check in UserPromptSubmit hook for lesson staleness
4. **Diary integration**: Use `/diary` command consistently and convert to lessons weekly

## Detection Method

CEO noticed the GitHub Pages lessons page was not updating daily.

## Correct Behavior

Every session should end with either:
- A new lesson captured (if something was learned)
- Explicit statement: "No new lessons to capture today - reviewed existing knowledge"

## Related Lessons

- LL_035: Failed to use RAG
- LL_054: RAG not actually used
- LL_044: Documentation hygiene mandate
