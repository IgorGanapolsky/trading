# Session Start Checklist

This checklist ensures critical tasks are reviewed at the start of each session.

## Daily Required Checks

### 1. Lesson Capture Review
- [ ] Check when the last lesson was captured: `ls -lt rag_knowledge/lessons_learned/ll_*.md | head -3`
- [ ] If >24 hours since last lesson, either:
  - Capture a new lesson from previous session learnings
  - Explicitly state: "No new lessons to capture - reviewed existing knowledge"

### 2. RAG Knowledge Currency
- [ ] Verify RAG index is current: `cat data/rag/lessons_indexing_stats.json`
- [ ] Re-index if stale: `python scripts/index_lessons.py`

### 3. System State
- [ ] Check data freshness: `data/system_state.json` should be <4 hours old
- [ ] Review any deferred items from previous sessions

## Weekly Checks (Monday)

### Diary-to-Lessons Conversion
- [ ] Review `~/.claude/memory/diary/` entries from the past week
- [ ] Convert significant diary entries to formal lessons using `/capture-learning`
- [ ] Run `/reflect` to generate new rules from patterns

### 4. Position Protection (Phil Town Rule #1)
- [ ] Check trailing stops status: `python3 -c "import json; s=json.load(open('data/system_state.json')); print(s.get('trailing_stops', 'NOT CONFIGURED'))"`
- [ ] If NOT CONFIGURED and positions exist, trigger CI: `set-trailing-stops` task
- [ ] Verify all positions have stop-loss protection before market opens

## Deferred Items

Track items that need follow-up but aren't blocking:

1. **URGENT (Jan 8, 2026)**: Trigger `set-trailing-stops` workflow before 9:30 AM ET
   - 5 positions with $1,187.60 unrealized gains currently UNPROTECTED
   - Command: `gh workflow run claude-agent-utility.yml -f task=set-trailing-stops`

---

*Last updated: January 7, 2026*
