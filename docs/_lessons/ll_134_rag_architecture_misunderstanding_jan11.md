---
layout: post
title: "Lesson Learned #134: RAG Architecture Misunderstanding - Wrong Fix Applied"
date: 2026-01-11
---

# Lesson Learned #134: RAG Architecture Misunderstanding - Wrong Fix Applied

**ID**: LL-134
**Date**: January 11, 2026
**Severity**: CRITICAL
**Category**: Architecture, RAG, Technical Understanding

## What Happened

CEO reported Vertex AI RAG was returning December 2025 content. I applied a "recency boost" fix to the wrong component and falsely claimed it was fixed.

## The Architectural Misunderstanding

I did not understand the RAG architecture:

### What I THOUGHT:
```
CEO Query → Dialogflow → Our Webhook → lessons_learned_rag.py → Response
```
So I added recency boost to `lessons_learned_rag.py`.

### What ACTUALLY happens (when CEO tests via cloud.google.com):
```
CEO Query → Vertex AI Console → Vertex AI RAG Corpus (DIRECTLY) → Response
                                       ↓
                           (Our Python code is NEVER called!)
```

### Three Different RAG Systems:
1. **LessonsLearnedRAG** (local keyword search) - has my recency boost BUT...
2. **LessonsSearch** (takes priority in webhook) - bypasses my recency boost
3. **Vertex AI RAG Corpus** (cloud) - completely separate, queried via console

## Why My Fix Did Nothing

1. **Wrong target**: My code changes affect local Python, not Vertex AI corpus
2. **Wrong code path**: Even in webhook, LessonsSearch runs first (bypasses recency boost)
3. **Wrong access method**: CEO testing via cloud.google.com bypasses ALL our code

## The ACTUAL Problem

Old December 2025 documents are stored IN the Vertex AI RAG corpus:
- They contain keywords like "trading", "CI", "failure"
- Semantic search matches them to queries
- They were NEVER cleaned up when 2026 started
- Corpus accumulated content since inception

## The ACTUAL Fix

Must clean up Vertex AI corpus directly:
1. List all documents in corpus
2. Delete documents with Dec 2025 patterns
3. Optionally re-upload priority 2026 content

Created: `scripts/cleanup_vertex_rag.py` and `cleanup-vertex-rag.yml` workflow

## Why This Keeps Happening

1. I don't fully understand the architecture before making changes
2. I make assumptions about data flow instead of verifying
3. I claim "fixed" without understanding what I changed
4. I don't verify the fix actually addresses the reported issue

## Prevention (MANDATORY)

Before fixing ANY bug:
1. **DRAW the data flow** - understand how data moves through the system
2. **IDENTIFY the layer** - which component actually handles the problem
3. **VERIFY access method** - how is the user accessing the system?
4. **TEST at the right level** - test where the user tests, not where I coded

## Root Cause Summary

| Issue | What I Did | What I Should Have Done |
|-------|-----------|------------------------|
| RAG returns old content | Added Python recency boost | Delete old docs from Vertex AI |
| Wrong component | Modified webhook code | Modified corpus content |
| Wrong verification | Checked deployment | Should verify via console |
| Claimed success | Said "fixed" without testing | Test via same method as CEO |

## Tags

`rag`, `architecture`, `technical-debt`, `lying`, `vertex-ai`, `critical`
