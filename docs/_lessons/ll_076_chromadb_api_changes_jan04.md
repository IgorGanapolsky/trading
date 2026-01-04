---
title: "ChromaDB v0.6.0 API Breaking Changes"
date: 2026-01-04
category: infrastructure
severity: medium
tags: [chromadb, api, testing, dependencies]
---

## What Happened

Test `test_vector_db_has_data` failed after upgrading to ChromaDB v0.6.0 with error:
```
NotImplementedError: In Chroma v0.6.0, list_collections only returns collection names
```

## Root Cause

ChromaDB v0.6.0 changed the `list_collections()` API:
- **Before**: Returns `Collection` objects with `.name` attribute
- **After**: Returns strings (collection names only)

The test used `hasattr(first_collection, "name")` which now raises `NotImplementedError`.

## Solution

Use `isinstance()` check instead of `hasattr()`:

```python
# Bad (fails in 0.6.0)
if hasattr(first_collection, "name"):
    col = first_collection

# Good (works in all versions)
if isinstance(first_collection, str):
    col = client.get_collection(first_collection)
else:
    col = first_collection
```

## Prevention

1. **Pin major versions** in requirements.txt (e.g., `chromadb>=0.6.0,<0.7.0`)
2. **Read changelogs** before upgrading dependencies
3. **Test after upgrades** - run full test suite after any dependency update

## Related

- ChromaDB migration guide: https://docs.trychroma.com/deployment/migration
- PR #1030: Fixed the test
