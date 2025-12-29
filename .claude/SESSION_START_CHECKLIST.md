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

## Deferred Items

Track items that need follow-up but aren't blocking:

1. *(Add deferred items here)*

---

*Last updated: December 29, 2025*
