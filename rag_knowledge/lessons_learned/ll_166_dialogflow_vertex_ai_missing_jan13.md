# Lesson Learned: Dialogflow Webhook Missing Vertex AI - Only Local Keyword Search

**ID**: ll_166_dialogflow_vertex_ai_missing_jan13
**Date**: 2026-01-13
**Severity**: HIGH

## Problem
Dialogflow webhook was falling back to local keyword search instead of using Vertex AI semantic search. CEO saw "Based on our lessons learned (local search):" instead of synthesized answers from Gemini.

## Root Cause
1. **Dockerfile.webhook** explicitly excluded Vertex AI:
   - No `google-cloud-aiplatform` or `vertexai` packages
   - Did NOT copy `src/rag/vertex_rag.py`
   - Comment said: "not vertex_rag.py which needs google.cloud"

2. **deploy-dialogflow-webhook.yml** missing environment variables:
   - No `GOOGLE_CLOUD_PROJECT` set
   - No `VERTEX_AI_LOCATION` set
   - Without these, Vertex AI RAG cannot initialize

## Fix
1. Updated Dockerfile.webhook:
   - Added `google-cloud-aiplatform>=1.72.0` and `vertexai>=1.72.0`
   - Added `COPY src/rag/vertex_rag.py src/rag/`

2. Updated deploy-dialogflow-webhook.yml:
   - Added `--set-env-vars "GOOGLE_CLOUD_PROJECT=...,VERTEX_AI_LOCATION=..."`

## Impact
- Dialogflow was useless for answering CEO questions
- Only dumped keyword-matched lessons instead of synthesizing answers
- No semantic search capability despite Vertex AI being available

## Prevention
1. Always verify Cloud Run environment variables after deployment
2. Test Dialogflow responses show "Vertex AI RAG" not "local search"
3. Include Vertex AI deps in Dockerfile when semantic search is required

## Tags
dialogflow, vertex-ai, rag, cloud-run, deployment, semantic-search
