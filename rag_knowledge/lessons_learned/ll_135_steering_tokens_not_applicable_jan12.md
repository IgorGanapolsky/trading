# Lesson Learned: Steering Tokens Research Not Applicable to Our Architecture

**ID**: LL_135
**Date**: 2026-01-12
**Severity**: LOW
**Category**: Architecture
**Tags**: llm, research, steering-tokens, prompt-engineering, technology-evaluation

## Incident Summary

Evaluated "Compositional Steering Tokens" paper (Jan 2026) claiming learned tokens can replace long behavior prompts for LLM control. Determined this technique is not actionable for our trading system.

## Root Cause

The technique requires:
1. Access to model weights (we use Claude via API - no access)
2. Ability to train custom token embeddings (not possible through Anthropic's interface)
3. Self-distillation training on the base model (only model developers can do this)

This is a **research technique for model developers** (Anthropic, OpenAI), not for API consumers like us.

## Impact

No negative impact - correctly identified as non-applicable before wasting implementation effort. Time spent: ~15 minutes research. Value: Prevents future re-evaluation of same technology.

## Prevention Measures

When evaluating new LLM control techniques, ask:
1. Does it require model weight access? → Not applicable to us
2. Does it require fine-tuning/training? → Not applicable to us
3. Can it be done via API/prompts only? → Potentially applicable

## Detection Method

Deep research before implementation attempt. Read actual paper requirements vs our capabilities.

## Related Lessons

- Our current architecture (CLAUDE.md + hooks + RAG + skills) is correct for API-level access
- Prompt engineering remains our primary LLM control mechanism
- Don't chase academic research that requires capabilities we don't have
