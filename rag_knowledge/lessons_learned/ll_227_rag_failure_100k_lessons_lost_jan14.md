# Lesson Learned: RAG System Gap - $100K Account Period Investigation Needed

**ID**: LL-203
**Date**: January 14, 2026
**Severity**: HIGH (was CRITICAL - revised after verification)
**Category**: Data Gap / Investigation Required

## What We Know (Verified)

1. **Local RAG files** (`rag_knowledge/lessons_learned/`) contain 49 lessons
2. **Earliest local lesson**: ll_131 (January 12, 2026)
3. **Vertex AI RAG** was created January 5, 2026 (per `vertex_rag.py` header)
4. **Blog sync script** only reads from local files, not Vertex AI

## What We DON'T Know (Unverified)

1. What lessons exist in Vertex AI datastore (can't query from sandbox)
2. Whether lessons were recorded during $100K period but stored in Vertex AI only
3. Whether there's an archive of older lessons elsewhere
4. The actual root cause of the gap between Jan 5 (RAG created) and Jan 12 (first local lesson)

## Original Claim (CORRECTED)

The original version of this lesson claimed "ZERO lessons were recorded" during the $100K period. **This was an incorrect claim based on incomplete information.**

The CTO (Claude) could only verify local files, not the Vertex AI datastore. The absence of local files does not prove lessons weren't recorded elsewhere.

## What IS True

- Local RAG files start from Jan 12
- The blog only shows lessons from Jan 7, 12, 13, 14
- There's a visibility gap for the $100K account period on the blog
- The blog sync relies on local files only

## Action Items

1. **Investigate**: Query Vertex AI RAG from GitHub Actions to see what's stored there
2. **Sync**: If lessons exist in Vertex AI, sync them to local files
3. **Document**: Once verified, document the actual state of historical lessons
4. **Fix Blog**: Ensure all lessons (local + Vertex AI) appear on blog

## Lesson for CTO

**Never claim data loss without verifying all storage locations.**

The original lesson violated the honesty protocol by making definitive claims without evidence.

## Tags

`data-gap`, `investigation-needed`, `vertex-ai`, `blog-sync`
