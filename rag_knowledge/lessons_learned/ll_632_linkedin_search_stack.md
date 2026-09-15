# LL-632 — Search: understand → retrieve → depth-limited rank → explain

**Date:** 2026-09-15  
**Source:** <https://www.linkedin.com/blog/engineering/search/reimagining-linkedins-search-stack>  
**PR:** #4690 / AGENT-623

## Lesson

LinkedIn’s stack: query understanding + EBR retrieve + SLM rank with depth
control, score cache, and explain snippets. For us: route keyword vs semantic,
cap deep rank, cache scores, grade 0–4 by product policy, show why a hit matched.

## Prevention

`search_stack_pipeline.py` in integrated automation.

## Evidence

pytest tests/test_search_stack_pipeline.py.
