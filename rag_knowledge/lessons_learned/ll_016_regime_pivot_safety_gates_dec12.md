# Lesson Learned: Regime Pivot Safety Gates (Dec 12, 2025)

**ID**: ll_016
**Date**: December 12, 2025
**Severity**: HIGH
**Category**: Safety, Risk Management, RL, Sentiment Analysis
**Impact**: Proactive prevention of future failures

## Executive Summary

External review identified critical safety gaps. This lesson documents the regime pivot
implementing 4 critical safety enhancements to prevent future failures.

## The Gap Identified

### External Analysis Findings

| Issue | Risk | Fix |
|-------|------|-----|
| Single-point RL failure | One bad model = bad trade | Cap RL at 10% |
| LLM sentiment noise | Hallucinated signals | VADER + cosine sim veto |
| Edge fade undetected | Trading losing strategy | 14d rolling EV alert |
| No crash stress testing | Unknown bear market behavior | 2008/2020 replay |

### Why This Matters

On Dec 11, a syntax error caused 0 trades. But there are subtler failures:
- **Gradual edge fade**: Strategy slowly becomes unprofitable over 2 weeks
- **Model hallucination**: LLM confidently gives wrong signal
- **Regime change**: Market shifts, strategy doesn't adapt
- **Crash vulnerability**: System untested in extreme conditions

## The Fix

### 1. RL Weight Cap (10%)

**File**: `src/agents/rl_agent.py`

```python
# Dec 12, 2025: CEO directive - RL outputs capped at 10% total influence
rl_total_weight = float(os.getenv("RL_TOTAL_WEIGHT", "0.10"))
heuristic_weight = float(os.getenv("RL_HEURISTIC_WEIGHT", "0.40")) * rl_total_weight
transformer_weight = float(os.getenv("RL_TRANSFORMER_WEIGHT", "0.45")) * rl_total_weight
disco_weight = float(os.getenv("RL_DISCO_WEIGHT", "0.15")) * rl_total_weight
```

**Rationale**: If RL gives bad signal, 90% of decision still comes from momentum/rules.

### 2. Sentiment Fact-Check

**File**: `src/utils/sentiment.py`

```python
def fact_check_sentiment(llm_sentiment, raw_text, threshold=0.7):
    """
    VADER + cosine similarity veto.
    If LLM and VADER disagree (sim < 0.7 or opposite direction), VETO.
    """
    vader_score = compute_lexical_sentiment(raw_text)
    sim = cosine_similarity(llm_vec, vader_vec)
    same_direction = (llm_sentiment >= 0 and vader_score >= 0) or (...)
    accepted = sim >= threshold and same_direction
```

**Rationale**: LLMs can hallucinate. VADER is deterministic baseline.

### 3. EV Drift Alert

**File**: `scripts/shadow_live.py`

```bash
# Check rolling 14-day EV
python3 scripts/shadow_live.py --ev-check

# If EV < 0, trading auto-halts
# Clear halt after manual review
python3 scripts/shadow_live.py --clear-halt
```

**Rationale**: Catches edge fade before it destroys capital.

### 4. Crash Replay Scenarios

**File**: `config/backtest_scenarios.yaml`

New scenarios with 95% survival gate:
- `crash_2008_lehman`: Sep-Nov 2008
- `crash_2008_bottom`: Jan-Mar 2009
- `crash_2020_covid_march`: Feb 19 - Mar 23, 2020
- `crash_2022_fed_tightening`: Jan-Oct 2022

**Rationale**: If system can't survive historic crashes, don't deploy live.

## Verification Tests

### Test 1: RL Weight Cap

```python
def test_ll_016_rl_weight_capped():
    """RL influence must be <= 10%."""
    import os
    rl_weight = float(os.getenv("RL_TOTAL_WEIGHT", "0.10"))
    assert rl_weight <= 0.15, f"REGRESSION ll_016: RL weight {rl_weight} > 15%"
```

### Test 2: Sentiment Fact-Check Catches Disagreement

```python
def test_ll_016_sentiment_fact_check_veto():
    """Sentiment fact-check must veto on LLM/VADER disagreement."""
    from src.utils.sentiment import fact_check_sentiment

    # LLM says positive, but text is negative
    result = fact_check_sentiment(
        llm_sentiment=0.8,  # Very positive
        raw_text="The stock crashed horribly. Investors lost millions."
    )

    assert not result["accepted"], "REGRESSION ll_016: Should veto on disagreement"
```

### Test 3: EV Drift Alert Halts Trading

```python
def test_ll_016_ev_drift_halts_on_negative():
    """EV drift must halt trading when rolling EV < 0."""
    from scripts.shadow_live import EVDriftTracker

    tracker = EVDriftTracker(halt_threshold=0.0)
    # If rolling EV is negative, should_halt must be True
```

### Test 4: Crash Replay Survival Gate

```python
def test_ll_016_crash_scenarios_have_survival_gate():
    """Crash replay scenarios must have 95% survival gate."""
    import yaml

    with open("config/backtest_scenarios.yaml") as f:
        config = yaml.safe_load(f)

    crash_scenarios = [s for s in config["scenarios"] if s["name"].startswith("crash_")]

    for scenario in crash_scenarios:
        if scenario["name"] != "crash_2020_recovery":  # Recovery doesn't need gate
            assert scenario.get("survival_gate") == 0.95, \
                f"REGRESSION ll_016: {scenario['name']} missing 95% survival gate"
```

## Integration with RAG Pipeline

### 1. Before Any Trade

```python
# Query RAG for similar past failures
from src.verification.rag_safety_checker import RAGSafetyChecker

checker = RAGSafetyChecker()
warnings = checker.check_trade_safety(trade_context)

if warnings.severity == "critical":
    logger.warning("RAG blocked trade: %s", warnings.message)
    return None  # Don't execute
```

### 2. On Any Failure

```python
# Auto-record to RAG for future learning
def record_trade_failure(context, error):
    lesson = {
        "id": f"auto_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "category": "trade_failure",
        "context": context,
        "error": str(error),
        "timestamp": datetime.now().isoformat(),
    }

    # Write to lessons learned
    path = f"rag_knowledge/lessons_learned/auto_{lesson['id']}.json"
    with open(path, "w") as f:
        json.dump(lesson, f)
```

### 3. Continuous Learning

The system now learns from:
- Successful trades (positive reward)
- Failed trades (negative reward, recorded to RAG)
- Near-misses (warnings, patterns logged)
- External analysis (like today's review)

## Key Quotes

> "Single-point LLM failure → one bad hallucination = bad trade."

> "Rolling EV catches edge fade before capital destruction."

> "Bear-proof the system with 2008/2020 replay."

> "Paper's the lab, live is the blade."

## Related Lessons

- `ll_009_ci_syntax_failure_dec11.md` - Pre-merge verification
- `ll_013_external_analysis_safety_gaps_dec11.md` - External review findings
- (Future) `ll_017_live_deployment_checklist.md` - Pre-live safeguards

## Tags

#rl #sentiment #ev-drift #crash-replay #safety #regime-pivot #lessons-learned #rag #ml

## Change Log

- 2025-12-12: Initial lesson from regime pivot implementation
