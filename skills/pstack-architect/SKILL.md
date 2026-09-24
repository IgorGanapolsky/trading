---
name: pstack-architect
description: "Design caller-first, type-safe interfaces and contracts with pre-implementation checkpoints before writing internal code. Use when adding new strategy modules, broker adapters, risk gates, or multi-agent bridges."
---

# pstack: /architect (Caller-First Interface Design)

The `/architect` skill implements caller-first system design from the **pstack** engineering playbook. It prohibits writing internal implementation code before the caller ergonomics, type boundaries, failure modes, and verification checkpoints are explicitly specified and reviewed.

---

## Operating Invariants

1. **Caller Ergonomics First**: Write the consumer's call site first. If the caller code looks clunky, verbose, or fragile, the architecture is flawed.
2. **Type Safety & Immutability**: Use frozen `@dataclass`, strict `typing`, and runtime validation for inputs and state.
3. **Explicit Error Boundaries**: Never return raw ambiguous types (e.g. `None` or bare dictionaries). Return Result/Option patterns or raise typed exceptions.
4. **Design Checkpoint Approval**: Summarize the contract and get checkpoint alignment before filling out implementation bodies.

---

## Architectural Design Steps

### Step 1: Write Caller Usage Code
Construct the ideal caller snippet:
```python
# How the strategy caller should look:
decision = risk_engine.evaluate_spread(
    ticker="SPY",
    short_delta=0.15,
    max_risk_dollars=500.0,
    account_equity=100_000.0,
)

if not decision.is_permitted:
    logger.warning("Trade rejected: %s", decision.rejection_reason)
    return

order_spec = decision.order_spec  # Invariant: non-null when is_permitted is True
```

### Step 2: Define Data Contracts
Specify immutable domain models:
```python
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

@dataclass(frozen=True)
class SpreadOrderSpec:
    symbol: str
    expiration: str
    short_strike: float
    long_strike: float
    contracts: int
    limit_price: float

@dataclass(frozen=True)
class RiskDecision:
    is_permitted: bool
    rejection_reason: str | None = None
    order_spec: SpreadOrderSpec | None = None
    evaluated_at: datetime = ...
```

### Step 3: Define Interface Signature & Invariants
```python
class RiskEngineProtocol(Protocol):
    def evaluate_spread(
        self,
        ticker: str,
        short_delta: float,
        max_risk_dollars: float,
        account_equity: float,
    ) -> RiskDecision:
        """Evaluate spread against portfolio kill switch and position limits.
        
        Invariants:
        - Must reject if live_blocked is True and TRADING_ENV is live.
        - Must reject if position size exceeds max_risk_dollars.
        - Must be side-effect free.
        """
        ...
```

### Step 4: Verification Checkpoints
Define how the implementation will be tested before writing it:
1. Unit test: Valid parameters generate permitted `RiskDecision`.
2. Unit test: Sizing violation returns rejection with reason.
3. Unit test: Kill switch active returns immediate rejection without network calls.
4. Dry-run test: Execution against paper simulator produces valid order spec.
