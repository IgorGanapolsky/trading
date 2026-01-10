---
layout: post
title: "CI Failure Resolution - LanceDB Tests Skip Logic"
date: 2026-01-05
---

# CI Failure Resolution - LanceDB Tests Skip Logic

**Date**: 2026-01-05  
**Severity**: HIGH  
**Category**: ci_reliability

## Impact
CI was failing due to LanceDB tests directly importing optional dependencies

## Root Cause
Tests imported lancedb/fastembed without checking availability, causing ImportError in CI

## Solution
Added pytest.mark.skipif decorators to skip tests when LanceDB not installed

## Prevention Rules
- Always use pytest.importorskip or skipif for optional dependency tests
- Test locally without optional deps before pushing
- Follow the pattern: try/except import with AVAILABLE flag

## Evidence
- PR Merged: #1084
- Commit: 0879642
- Tests properly skipping: 12
- CI Status: success
