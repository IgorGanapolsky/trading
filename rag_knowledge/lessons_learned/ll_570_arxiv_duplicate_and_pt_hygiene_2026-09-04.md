# LL-570: Duplicate arXiv tree and tracked `*.pt` weights (2026-09-04)

**ID**: LL-570
**Date**: 2026-09-04
**Severity**: 3
**Category**: repository-hygiene

## Problem

`data/arxiv/` was a byte-identical copy of `rag_knowledge/arxiv/` (157 files). The ingest workflow `git add -f data/arxiv/` kept the duplicate in Git.

`*.pt` is gitignored, but `models/ml/grpo_trade_policy.pt` and `models/ml/rl_transformer_state.pt` were still tracked.

## Fix

- Stop tracking `data/arxiv/` and `*.pt`.
- Ingest workflow commits only `rag_knowledge/arxiv/` plus audit manifests.
- Hygiene audit errors on `data/arxiv/` and tracked `.pt`.

## Rule

Canonical arXiv corpus is `rag_knowledge/arxiv/`. Local ingest copies and PyTorch weights stay on disk, not in Git.

## Tags

#hygiene #arxiv #gitignore #technical-debt
