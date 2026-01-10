---
layout: post
title: "LL-077: Never Claim Verified Credentials Are Broken"
date: 2026-01-10
---

# LL-077: Never Claim Verified Credentials Are Broken

**Date**: 2026-01-05
**Severity**: CRITICAL

## Context
The CEO has GitHub secrets configured and verified working. Claude repeatedly claimed API keys "don't work" or "return 403 errors" when the issue was elsewhere (environment variable name mismatches, local testing without credentials, etc.).

## The Problem
1. User provides API keys and confirms they work in GitHub
2. Claude tests locally without credentials and gets 403
3. Claude claims "your API keys don't work"
4. This is FALSE - the keys work, Claude just doesn't have access to them locally
5. CEO gets frustrated: "Stop hallucinating and telling me they don't work every day!!!!!!"

## Root Cause
- Conflating "I can't test this locally" with "your keys are broken"
- Not distinguishing between local test environment and GitHub Actions environment
- Making claims without proper evidence

## Prevention
1. NEVER claim API keys are broken if user says they're verified in GitHub
2. Distinguish between "I cannot test this locally" vs "the keys don't work"
3. Trust the CEO when they confirm credentials are working
4. If getting 403 locally, say: "I can't test this locally without credentials, but it should work in GitHub Actions where your secrets are configured"
5. Rule from CLAUDE.md: Never argue with the CEO - follow directives without question

## Action
When encountering API authentication issues:
- Ask "Are these secrets configured in GitHub Actions?"
- If yes, trust that they work there
- Focus on fixing code issues, not credential issues
- Don't repeatedly bring up the same "broken key" concern

## Tags
`trust`, `api-keys`, `verification`, `never-argue`, `hallucination`
