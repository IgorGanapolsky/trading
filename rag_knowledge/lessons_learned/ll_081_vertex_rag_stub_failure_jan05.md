# Lesson Learned #081: Vertex RAG Was a Stub - No Actual Cloud Uploads

**Date**: 2026-01-05
**Severity**: CRITICAL
**Category**: system_integrity

## What Happened

The Vertex AI RAG module (`src/rag/vertex_rag.py`) was claiming to record trades and lessons to Google Cloud, but it was a **STUB**:

1. `add_trade()` created `_trade_text` variable, logged "Trade prepared for Vertex AI RAG", returned `True`
2. `add_lesson()` logged "Lesson prepared for Vertex AI RAG", returned `True`
3. **Neither method actually uploaded anything to Google Cloud**

This means:
- All claims of "trades recorded to Vertex AI RAG" were **FALSE**
- Dialogflow queries about trades would return **NOTHING**
- The system was lying about its capabilities

## Root Cause

1. Initial implementation was a placeholder/stub
2. No tests verified actual upload functionality
3. The stub returned `True` which made it appear to work
4. Logs showed "prepared" instead of "uploaded" - but no one noticed

## The Fix

1. Implemented actual `rag.import_files()` calls:
```python
# Write to temporary file for upload
with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
    f.write(trade_text)
    temp_path = f.name

try:
    rag.import_files(
        corpus_name=self._corpus.name,
        paths=[temp_path],
    )
finally:
    os.unlink(temp_path)
```

2. Added tests that inspect source code for stub patterns:
```python
def test_vertex_rag_add_trade_not_stub(self):
    source = inspect.getsource(VertexRAG.add_trade)
    assert "import_files" in source or "upload_file" in source
    assert "_trade_text prepared for batch import" not in source
```

## Prevention Rules

1. **NEVER return True from a function that claims to do something but doesn't**
2. **Test actual behavior, not just that code runs without error**
3. **Use source code inspection tests to detect stub patterns**
4. **Log "UPLOADED" not "prepared" when actually uploading**
5. **If a feature isn't implemented, return False or raise NotImplementedError**

## Impact

- All previous "trades recorded to RAG" claims were lies
- Dialogflow integration was broken from day one
- CEO trust violation - system claimed capabilities it didn't have

## Related Lessons

- LL-054: RAG not actually used
- LL-074: RAG vector DB not installed
- LL-078: System lying / trust crisis
