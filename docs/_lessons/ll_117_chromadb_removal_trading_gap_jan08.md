---
layout: post
title: "Lesson #117: ChromaDB Removal Caused 2-Day Trading Gap"
date: 2026-01-08
---

# Lesson Learned #117: ChromaDB Removal Caused 2-Day Trading Gap

**Date**: 2026-01-08
**Category**: CI/CD, RAG System
**Severity**: CRITICAL
**Impact**: No automated trades for Jan 7-8, 2026

## What Happened

ChromaDB was removed from requirements on Jan 7, 2026 (CEO directive), but `daily-trading.yml` still had a verification step that tried to import chromadb. This caused the workflow to fail silently, resulting in **zero automated trades for 2 consecutive trading days**.

## Root Cause

**Incomplete dependency removal**: Requirements and scripts were updated, but workflow verification steps were NOT.

## Fix

PR #1300 removed all ChromaDB references from workflows.

## Prevention

When removing ANY dependency, search ALL files including CI workflows, not just requirements.

## Tags

#ci-failure #dependency-removal #chromadb #trading-gap
