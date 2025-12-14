# Verification System Quick Start

**Quick reference for using the automated verification system.**

## Before Every PR Merge

```bash
# Run enhanced pre-merge gate (recommended)
python3 scripts/enhanced_pre_merge_gate.py

# Or use basic pre-merge gate
python3 scripts/pre_merge_gate.py
```

## After Merge (Automatic)

The GitHub Actions workflow automatically:
1. Runs post-merge verification
2. Checks system health
3. Monitors for failures

## Daily Failure Detection (Automatic)

Runs daily at 2 AM UTC:
- Detects CI failures
- Detects trading failures
- Auto-ingests lessons learned

## Manual Failure Detection

```bash
# Check CI failures and auto-ingest
python3 -m src.verification.automated_lesson_ingestion --check-ci --auto-ingest

# Check syntax for files
python3 -m src.verification.automated_lesson_ingestion --check-syntax file1.py file2.py
```

## What Gets Checked

### Pre-Merge
- ✅ Python syntax (all files)
- ✅ Critical imports (TradingOrchestrator, AlpacaExecutor, TradeGateway)
- ✅ ML anomaly detection (code complexity, patterns)
- ✅ RAG semantic search (similar past failures)
- ✅ Pattern matching (dangerous file patterns)

### Post-Merge
- ✅ System health
- ✅ Trading workflow status
- ✅ Import verification
- ✅ Performance metrics

## Common Issues

### "ML+RAG verification not available"
- Install dependencies: `pip install httpx sentence-transformers`
- Check RAG store exists: `data/rag/lessons_learned.json`

### "RAG safety checker not available"
- Ensure lessons learned directory exists: `rag_knowledge/lessons_learned/`
- Run ingestion: `python3 scripts/ingest_lessons_to_rag.py`

### "GitHub CLI not available"
- Install: `apt install gh` or `brew install gh`
- Authenticate: `gh auth login`

## Integration with CI/CD

The system is automatically integrated via:
- `.github/workflows/automated-verification.yml`

No manual setup required - runs on every PR and push to main.

## Key Commands

```bash
# Pre-merge check
python3 scripts/enhanced_pre_merge_gate.py

# Post-merge check
python3 -m src.verification.ml_rag_integrated_verifier --post-merge

# Failure detection
python3 -m src.verification.automated_lesson_ingestion --check-ci --auto-ingest

# Run tests
pytest tests/test_automated_verification_system.py -v
```

## Remember

**Always run pre-merge gate before merging PRs!**

The system learns from every failure - failures are automatically ingested into RAG for future prevention.
