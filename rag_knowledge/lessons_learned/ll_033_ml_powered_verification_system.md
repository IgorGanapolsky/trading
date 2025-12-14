# Lesson Learned: ML-Powered Verification System (Dec 14, 2025)

**ID**: LL-033
**Date**: December 14, 2025
**Severity**: HIGH
**Category**: Verification, ML, RAG, CI/CD
**Impact**: Proactive failure prevention

## Executive Summary

Implemented a comprehensive ML-powered verification system that learns from past failures and prevents repeat incidents. This system addresses gaps identified after the Dec 11 syntax error incident (LL-009) and other historical failures.

## The Problem

Our existing verification was reactive rather than proactive:
- Lessons were documented but not automatically applied
- CI failures weren't automatically ingested into the learning system
- Code changes weren't scored for risk based on past failures
- No continuous monitoring with ML anomaly detection

## The Solution

Created four interconnected components:

### 1. ML Lesson Pattern Detector (`src/verification/ml_lesson_pattern_detector.py`)

**What it does:**
- Detects patterns in past failures using machine learning
- Scores code changes for risk based on historical patterns
- Automatically learns from new failures
- Integrates with RAG for additional context

**Key features:**
- Pattern database with 6+ default patterns from known incidents
- Risk scoring from 0.0 to 1.0
- Automatic pattern extraction from error messages
- Prevention checklist generation

**Usage:**
```python
from src.verification.ml_lesson_pattern_detector import assess_pr_risk

result = assess_pr_risk(
    files_changed=["src/execution/alpaca_executor.py"],
    commit_message="Modify trading execution",
)
print(f"Risk: {result['risk_level']}, Can merge: {result['can_merge']}")
```

### 2. CI Failure Ingestion Pipeline (`src/verification/ci_failure_ingestion.py`)

**What it does:**
- Fetches failed GitHub Actions runs automatically
- Parses error logs to extract failure signatures
- Classifies failure types (syntax, import, test, lint, etc.)
- Ingests failures into RAG and ML systems

**Key features:**
- Uses `gh` CLI for GitHub integration
- Automatic error classification
- Stores failure history for analysis
- Creates lessons learned entries automatically

**Usage:**
```python
from src.verification.ci_failure_ingestion import CIFailureIngestionPipeline

pipeline = CIFailureIngestionPipeline()
results = pipeline.process_recent_failures(limit=10)
```

### 3. Semantic Code Risk Scorer (`src/verification/semantic_code_risk_scorer.py`)

**What it does:**
- Uses embeddings to understand code changes semantically
- Classifies change intent (feature, bugfix, refactor, etc.)
- Determines impact level (minimal to critical)
- Finds similar past failures using vector similarity

**Key features:**
- Supports OpenAI/OpenRouter API embeddings or local sentence-transformers
- Keyword fallback when no embeddings available
- Diff parsing and chunk analysis
- Confidence-weighted scoring

**Usage:**
```python
from src.verification.semantic_code_risk_scorer import score_diff_risk

result = score_diff_risk(diff_content, commit_message)
print(f"Score: {result['score']}, Impact: {result['impact']}")
```

### 4. Continuous ML Monitor (`src/verification/continuous_ml_monitor.py`)

**What it does:**
- Monitors trading health, code quality, ML models, and data quality
- Creates alerts for issues detected
- Tracks health history over time
- Provides unified health checking

**Key features:**
- Multiple health check types
- Alert severity levels (info, warning, error, critical)
- Health percentage calculation
- Alert resolution tracking

**Usage:**
```python
from src.verification.continuous_ml_monitor import run_health_check

result = run_health_check()
print(f"Status: {result['status']}, Health: {result['health_percentage']}%")
```

## Prevention Rules

### Rule 1: Run Risk Assessment Before Merge

Before merging any PR:
```bash
python3 -c "
from src.verification.ml_lesson_pattern_detector import assess_pr_risk
result = assess_pr_risk(['file1.py', 'file2.py'], diff_content='...')
print(f'Risk: {result[\"risk_level\"]}, Can merge: {result[\"can_merge\"]}')
"
```

### Rule 2: Process CI Failures Regularly

Set up a scheduled job to ingest CI failures:
```bash
python3 -c "
from src.verification.ci_failure_ingestion import CIFailureIngestionPipeline
pipeline = CIFailureIngestionPipeline()
pipeline.process_recent_failures()
"
```

### Rule 3: Monitor System Health Continuously

Run health checks periodically:
```bash
python3 src/verification/continuous_ml_monitor.py
```

### Rule 4: Add New Failures to Pattern Database

When a new failure occurs, add it to the pattern detector:
```python
from src.verification.ml_lesson_pattern_detector import MLLessonPatternDetector, FailureCategory, RiskLevel

detector = MLLessonPatternDetector()
detector.learn_from_failure(
    error_message="New error type",
    files_involved=["affected_file.py"],
    category=FailureCategory.SYNTAX_ERROR,
    prevention="How to prevent this",
    risk_level=RiskLevel.HIGH,
)
```

## Tests

Comprehensive tests in `tests/test_comprehensive_rag_verification.py`:

- `TestLessonsLearnedRAG`: RAG functionality tests
- `TestMLLessonPatternDetector`: ML pattern detector tests
- `TestCIFailureIngestion`: CI failure ingestion tests
- `TestSemanticCodeRiskScorer`: Semantic risk scorer tests
- `TestIntegration`: End-to-end integration tests
- `TestRegressionPrevention`: Regression tests for known incidents

Run tests:
```bash
pytest tests/test_comprehensive_rag_verification.py -v
```

## Metrics to Track

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Risk score before merge | < 0.3 | > 0.7 |
| CI failures ingested | 100% | Any missed |
| Pattern database size | Growing | Stagnant |
| Health check pass rate | 100% | < 75% |
| Alert resolution time | < 24h | > 48h |

## Key Quotes

> "The best time to prevent a bug is before it's merged."

> "Every CI failure is a lesson waiting to be learned."

> "ML-powered verification catches what humans miss."

> "Continuous monitoring beats post-mortem analysis."

## Related Lessons

- `ll_009_ci_syntax_failure_dec11.md` - Original syntax error incident
- `ll_012_deep_research_safety_improvements_dec11.md` - Safety improvements
- `ll_018_pl_verification_failure_dec12.md` - Verification gaps

## Tags

#ml #rag #verification #ci #automation #prevention #lessons-learned #patterns

## Change Log

- 2025-12-14: Initial implementation
- 2025-12-14: Added comprehensive tests
- 2025-12-14: Created PR #628
