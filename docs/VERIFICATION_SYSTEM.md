# Automated Verification System with ML + RAG Integration

**Created**: December 13, 2025  
**Purpose**: Prevent future mistakes by learning from past failures using ML anomaly detection and RAG semantic search.

## Overview

This system combines:
1. **ML Anomaly Detection** - Pattern recognition for code, config, and trading anomalies
2. **RAG Semantic Search** - Finds similar past failures using embeddings
3. **Automated Lesson Ingestion** - Automatically records failures into lessons learned
4. **Continuous Monitoring** - Post-merge verification and daily failure detection

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Pre-Merge Verification                    │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │ ML Anomaly   │  │ RAG Semantic │  │ Pattern      │    │
│  │ Detection    │→ │ Search       │→ │ Matching     │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
│         ↓                  ↓                  ↓              │
│  ┌──────────────────────────────────────────────────────┐ │
│  │         Integrated Verification Result                │ │
│  │  - Risk Score (0-100)                                 │ │
│  │  - ML Anomalies                                       │ │
│  │  - RAG Warnings                                       │ │
│  │  - Similar Past Lessons                               │ │
│  └──────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              Post-Merge Monitoring                          │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │ CI Failure   │  │ Trading      │  │ Import/Syntax│    │
│  │ Detection    │  │ Failure      │  │ Detection    │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
│         ↓                  ↓                  ↓              │
│  ┌──────────────────────────────────────────────────────┐ │
│  │         Automated Lesson Ingestion                    │ │
│  │  - Generate Markdown Lesson                           │ │
│  │  - Add to RAG JSON Store                              │ │
│  │  - Update ML Baselines                                │ │
│  └──────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. Automated Lesson Ingestion (`src/verification/automated_lesson_ingestion.py`)

**Purpose**: Automatically detect failures and ingest them into RAG.

**Features**:
- CI/CD failure detection via GitHub CLI
- Syntax error detection in Python files
- Import error detection for critical modules
- Trading failure detection from system state
- Automatic markdown generation and RAG ingestion

**Usage**:
```bash
# Check CI failures and auto-ingest
python3 -m src.verification.automated_lesson_ingestion --check-ci --auto-ingest

# Check syntax for specific files
python3 -m src.verification.automated_lesson_ingestion --check-syntax file1.py file2.py

# Check imports
python3 -m src.verification.automated_lesson_ingestion --check-imports "src.orchestrator.main"
```

### 2. ML+RAG Integrated Verifier (`src/verification/ml_rag_integrated_verifier.py`)

**Purpose**: Comprehensive verification combining ML and RAG.

**Features**:
- Pre-merge verification with ML anomaly detection
- RAG semantic search for similar past failures
- Pattern matching against known failure modes
- Post-merge health checks
- ML baseline updates from lessons learned

**Usage**:
```bash
# Pre-merge verification
python3 -m src.verification.ml_rag_integrated_verifier \
  --pre-merge \
  --files file1.py file2.py \
  --commit-msg "fix: update logic"

# Post-merge verification
python3 -m src.verification.ml_rag_integrated_verifier --post-merge
```

### 3. Enhanced Pre-Merge Gate (`scripts/enhanced_pre_merge_gate.py`)

**Purpose**: User-friendly script that runs all verification checks.

**Features**:
- Auto-detects changed files from git
- Runs basic syntax/import checks
- Runs ML+RAG integrated verification
- Provides clear pass/fail output

**Usage**:
```bash
# Auto-detect changes
python3 scripts/enhanced_pre_merge_gate.py

# Specify files manually
python3 scripts/enhanced_pre_merge_gate.py --files file1.py file2.py
```

## GitHub Actions Integration

### Workflow: `automated-verification.yml`

**Triggers**:
- Pull requests (pre-merge verification)
- Pushes to main (post-merge monitoring)
- Daily schedule (failure detection)
- Manual dispatch

**Jobs**:

1. **pre-merge-verification**: Runs enhanced pre-merge gate on PRs
2. **post-merge-monitoring**: Verifies system health after merge
3. **failure-detection**: Daily automated failure detection and lesson ingestion
4. **test-verification-system**: Runs test suite

## Prevention Examples

### Example 1: Syntax Error Prevention (ll_009)

**Past Failure**: Syntax error merged to main, broke trading.

**Prevention**:
```python
# Pre-merge gate automatically checks syntax
python3 scripts/enhanced_pre_merge_gate.py
# → Detects syntax error
# → Blocks merge
# → Shows similar past failure (ll_009)
```

### Example 2: F-String Syntax (ll_024)

**Past Failure**: Python 3.12+ incompatible f-string syntax.

**Prevention**:
```python
# ML anomaly detector flags complex f-strings
# RAG search finds ll_024
# Warning: "Similar past failure: f-string syntax error"
```

### Example 3: Large PR Pattern

**Past Failure**: 94-file PR caused production incident.

**Prevention**:
```python
# RAG safety checker detects large PR
# Pattern: >10 files changed
# Warning: "Large PRs have caused production incidents"
```

## ML Feedback Loop

The system learns from lessons learned:

1. **Failure Detected** → Ingested into RAG
2. **ML Baselines Updated** → Anomaly thresholds adjusted
3. **Future Similar Changes** → Higher risk score
4. **Prevention Improved** → Fewer false negatives

## RAG Integration

Lessons learned are stored in:
- **Markdown**: `rag_knowledge/lessons_learned/ll_*.md`
- **JSON**: `data/rag/lessons_learned.json`
- **Vector Store**: ChromaDB (via `src/rag/lessons_learned_rag.py`)

Semantic search uses:
- OpenAI embeddings (via OpenRouter) - primary
- sentence-transformers (local) - fallback
- Keyword search - final fallback

## Testing

Run comprehensive tests:
```bash
pytest tests/test_automated_verification_system.py -v
```

Tests cover:
- Syntax error detection
- Import error detection
- Failure ingestion
- Pre-merge verification
- Post-merge verification
- Integration pipeline
- Regression prevention

## Metrics

Track verification effectiveness:
- **Pre-merge block rate**: % of PRs blocked by verification
- **False positive rate**: % of blocks that were false alarms
- **Failure detection rate**: % of failures caught before merge
- **Lesson ingestion rate**: % of failures automatically ingested

## Future Enhancements

1. **ML Model Training**: Train custom anomaly detection model on historical failures
2. **Real-time Monitoring**: Continuous verification during development
3. **Predictive Alerts**: Predict failures before they occur
4. **Cross-Repository Learning**: Learn from failures in other projects

## Key Files

| File | Purpose |
|------|---------|
| `src/verification/automated_lesson_ingestion.py` | Failure detection & ingestion |
| `src/verification/ml_rag_integrated_verifier.py` | Integrated ML+RAG verification |
| `scripts/enhanced_pre_merge_gate.py` | User-friendly pre-merge script |
| `.github/workflows/automated-verification.yml` | GitHub Actions integration |
| `tests/test_automated_verification_system.py` | Comprehensive test suite |

## Related Documentation

- `rag_knowledge/lessons_learned/ll_009_ci_syntax_failure_dec11.md` - Syntax error incident
- `rag_knowledge/lessons_learned/ll_024_fstring_syntax_error_dec13.md` - F-string syntax incident
- `docs/CI_ARCHITECTURE.md` - CI/CD architecture
- `src/verification/README.md` - Verification module overview
