
## LL-246: Mixture-of-Thought (MoT) Evaluation - FLUFF
**Date**: 2026-01-19
**Category**: Resource Evaluation
**Verdict**: FLUFF - Not applicable to our system

**What it is**: Academic ML framework for training LLMs with multi-modal reasoning (natural language, code, truth-tables). Improves benchmark accuracy by 11.7pp on FOLIO/ProofWriter.

**Why not applicable**: 
- MoT is a MODEL TRAINING technique
- We consume pre-trained APIs (Claude, Kimi K2, Mistral)
- We don't train models - zero applicability
- Would require: training infrastructure, datasets, GPU compute

**What we already have**:
- ChainOfVerification (CoVe) - inference-time verification
- DebateAgents - multi-perspective reasoning
- BATS ModelSelector - intelligent model routing

**Reference**: https://arxiv.org/abs/2505.15817

**Lesson**: Distinguish training-time techniques (require ML infra) from inference-time techniques (work with APIs). Only inference-time techniques are relevant to our system.
