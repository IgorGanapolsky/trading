---
layout: post
title: "---"
date: 2026-01-06
---

---
layout: post
title: "Lesson Learned #090: Vertex AI RAG Works in CI Only (Sandbox SSL Limitation)"
date: 2026-01-06
---

# Lesson Learned #090: Vertex AI RAG Works in CI Only

**ID**: LL-090
**Date**: January 6, 2026
**Severity**: MEDIUM
**Category**: Infrastructure, RAG

## The Issue

Vertex AI RAG cannot connect from the local Claude Code sandbox due to SSL certificate interception:

```
SSL_ERROR_SSL: CERTIFICATE_VERIFY_FAILED: self signed certificate in certificate chain
```

## Root Cause

The sandboxed environment routes all HTTPS traffic through an intercepting proxy with a self-signed certificate. Google APIs (Vertex AI, Gemini) reject this as a security measure.

## Evidence

- virtualenv with google-cloud-aiplatform: SSL handshake fails
- google-generativeai package: SSL handshake fails
- All Google API endpoints: Blocked by proxy certificate

## Solution

**Vertex AI RAG works in GitHub Actions CI** where:
- Direct internet access is available
- `GCP_SA_KEY` secret provides service account credentials
- `GOOGLE_API_KEY` secret is set
- Project ID: `igor-trading-2025-v2`

## Trade Recording Architecture

| Environment | ChromaDB | Vertex AI RAG | Status |
|-------------|----------|---------------|--------|
| Local Sandbox | ✅ Works | ❌ Blocked | Partial |
| GitHub Actions | ✅ Works | ✅ Works | Full |

## Lesson

- Accept that Vertex AI is CI-only for now
- ChromaDB provides local RAG functionality
- All production trades go through CI workflows which have full Vertex AI access
