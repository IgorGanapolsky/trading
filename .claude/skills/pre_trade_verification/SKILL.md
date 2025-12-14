# Pre-Trade Verification Skill

## Purpose

**MANDATORY** verification before every trade execution. Uses RAG to search lessons learned, validates signals, and enforces circuit breakers.

## When to Use

- **ALWAYS** before executing any trade
- When creating new trading signals
- When reviewing trading strategy changes
- When debugging why a trade was blocked

## Quick Start

```python
from src.verification.pre_trade_check import PreTradeVerifier
from src.core.unified_domain_model import factory, TradeAction

verifier = PreTradeVerifier()

# Create signal
btc = factory.create_crypto_symbol("BTCUSD")
signal = factory.create_signal(btc, TradeAction.BUY, confidence=0.75, source="strategy")

# VERIFY BEFORE TRADING
result = verifier.verify(signal)

if result.approved:
    execute_trade(signal)
else:
    print(f"BLOCKED: {result.reasons}")
    print(f"Relevant lessons: {result.lessons_found}")
```

## Components

### 1. RAG Lessons Lookup
Searches 35+ lessons learned before every trade:
```python
lessons = verifier.rag.search("crypto BUY volatility")
critical = verifier.rag.get_critical_lessons()
```

### 2. Circuit Breakers

| Check | Limit |
|-------|-------|
| Max crypto trade | $50 |
| Max equity trade | $100 |
| Min BUY confidence | 65% |
| Min SELL confidence | 60% |
| Max daily trades | 10 |
| Symbol cooldown | 30 min |

### 3. Anomaly Detection
- Extreme confidence warning (>95%)
- Weekend equity trading
- After-hours trading

### 4. UDM Validation
Full validation using SHACL-style rules from `unified_domain_model.py`

## Verification Result

```python
result = verifier.verify(signal)

result.approved        # bool: Trade allowed?
result.reasons         # List[str]: Block reasons
result.warnings        # List[str]: Non-blocking warnings
result.lessons_found   # List[Dict]: Relevant lessons
result.checks_passed   # List[str]: Passed checks
```

## Integration Example

```python
# In trading strategy
class TradingStrategy:
    def __init__(self):
        self.verifier = PreTradeVerifier()

    def execute_signal(self, signal: Signal) -> bool:
        # MANDATORY VERIFICATION
        result = self.verifier.verify(signal)

        if not result.approved:
            logger.warning(f"Trade blocked: {result.reasons}")
            return False

        if result.warnings:
            logger.info(f"Warnings: {result.warnings}")

        # Proceed with trade
        return self._execute(signal)
```

## Audit Trail

All verifications logged to:
```
data/verification_logs/verification_YYYYMMDD.jsonl
```

## Files

- `src/verification/pre_trade_check.py` - Main implementation
- `rag_knowledge/lessons_learned/` - 35+ lessons
- `data/verification_logs/` - Audit trail

## Critical Rule

**NEVER bypass verification.** Every blocked trade has a reason based on past mistakes.
