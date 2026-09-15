# LL-624 — Response cache before another model call

**Date:** 2026-09-15  
**Source:** <https://thenewstack.io/llm-response-caching-costs/>  
**PR:** #4690 / AGENT-623

## Lesson

Duplicate LLM questions still bill per token. Exact-match fingerprint of
query+context+model+settings+source+scope skips the call when unchanged.
Not the same as provider prompt caching. Never cache realtime market or
personal data. Measure hit_rate before claiming savings.

## Prevention

`scripts/llm_response_cache.py` + `ralph --llm-cache-stats`.

## Evidence

`pytest tests/test_llm_response_cache.py`.
