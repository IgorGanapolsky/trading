# RAG Knowledge Integration into Live Trading

**Date**: December 10, 2025
**Status**: ✅ IMPLEMENTED & TESTED
**Author**: Claude (CTO)

## Overview

Successfully integrated RAG knowledge (McMillan's Options as a Strategic Investment + TastyTrade research) directly into live trading decisions. Every options trade is now validated against expert knowledge BEFORE execution.

## What Was Built

### 1. RAGTradeAdvisor Class (`src/trading/rag_trade_advisor.py`)

High-level advisor that bridges RAG knowledge and trading execution:

**Key Features**:
- Queries RAG before each options trade
- Validates strategy vs IV regime (prevents disasters like buying expensive premium in high IV)
- Cross-checks sentiment signals with McMillan's expected move calculation
- Provides approve/reject decision with detailed reasoning
- Returns confidence scores and warnings

**Main Method**:
```python
advisor = RAGTradeAdvisor()

advice = advisor.get_trade_advice(
    ticker="SPY",
    strategy="iron_condor",
    iv_rank=65,
    sentiment="neutral",
    dte=30,
    stock_price=450.0,
    current_iv=0.18
)

if advice["approved"]:
    # Execute trade
else:
    # Reject: advice["rejection_reason"]
```

### 2. ExecutionAgent Integration (`src/agents/execution_agent.py`)

Modified `execute_option_trade()` method to consult RAG before execution:

**What Changed**:
- Added `enable_rag_validation` parameter (default: True)
- Lazy initialization of RAGTradeAdvisor
- Consults RAG before submitting orders
- BLOCKS trade if RAG rejects (returns `REJECTED_BY_RAG` status)
- Logs RAG metadata with every trade

**New Parameters**:
```python
execution_agent.execute_option_trade(
    option_symbol="SPY250117C00450000",
    side="sell_to_open",
    qty=1,
    order_type="limit",
    limit_price=2.50,
    # NEW: RAG validation parameters
    ticker="SPY",
    strategy="iron_condor",
    iv_rank=65,
    sentiment="neutral",
    dte=30,
    stock_price=450.0,
    current_iv=0.18
)
```

### 3. OptionsProfitPlanner Integration (`src/analytics/options_profit_planner.py`)

Updated `_auto_execute_theta()` to pass RAG validation parameters:

**What Changed**:
- Now passes ticker, strategy, IV rank, sentiment, DTE to ExecutionAgent
- Theta harvest opportunities validated against McMillan/TastyTrade rules
- Prevents auto-execution of suboptimal strategies

## IV Regime Validation (CRITICAL)

The most important feature: **prevents strategy hallucination**.

### IV Regime Rules

| IV Rank | Regime | Allowed Strategies | Forbidden Strategies |
|---------|--------|-------------------|---------------------|
| 0-20% | Very Low | Long calls, long puts, debit spreads | Iron condors, credit spreads, covered calls |
| 20-35% | Low | Long options, debit spreads, calendars | Iron condors, naked puts |
| 35-50% | Neutral | Both credit & debit work | None |
| 50-65% | High | Credit spreads, iron condors, covered calls | Long calls, long puts |
| 65-100% | Very High | Credit spreads, iron condors, short strangles | Long calls, long puts, debit spreads |

### Why This Matters

**DISASTER SCENARIO** (prevented by RAG):
- Sentiment signal: "SPY overbought, expect pullback"
- Naive system: "Buy puts!" ❌
- Problem: IV Rank = 85% (very high)
- Result: Buying expensive premium that gets IV crushed → Loss even if direction correct

**RAG VALIDATION**:
```python
advice = advisor.validate_strategy_vs_iv("long_put", iv_rank=85)
# Returns: (False, "Strategy long_put is FORBIDDEN in very_high IV regime")
```

## Knowledge Sources

### McMillan (18 chunks)
- Covered call writing fundamentals
- Naked put writing strategy
- Bull/bear spreads
- Straddles and strangles
- Calendar spreads
- Butterfly spreads
- Greeks (delta, gamma, theta, vega)
- Stop-loss rules
- Volatility trading
- Earnings strategies
- Exercise and assignment

### TastyTrade (16 chunks)
- Covered call mechanics
- IV Rank explained
- Credit spreads (bull put, bear call)
- Iron condor construction
- The Wheel strategy
- Theta decay curve
- Delta-based position sizing
- Gamma risk near expiration
- Vega and volatility exposure
- Position sizing rules
- Rolling mechanics
- Earnings volatility strategies
- Probability of OTM analysis

### Trading Rules (TastyTrade Research)
```python
{
    "entry_criteria": {
        "iv_rank_minimum": 30,
        "iv_rank_ideal": 50,
        "delta_range_short_puts": [0.16, 0.30],
        "dte_entry": [30, 45],
        "liquidity_minimum_open_interest": 100
    },
    "management_rules": {
        "take_profit_target_percent": 50,
        "max_dte_before_close": 21,
        "roll_trigger": "tested_side_breached",
        "max_loss_percent_portfolio": 5
    }
}
```

## Testing

### Test Results: ✅ ALL PASSED

**Test Script**: `scripts/test_rag_integration.py`

```bash
╔====================================================================╗
║               RAG INTEGRATION TEST SUITE                           ║
╚====================================================================╝

✅ McMillan chunks loaded: 18
✅ TastyTrade chunks loaded: 16
✅ IV regime validation: WORKING
✅ Long calls correctly FORBIDDEN in very high IV (85%)
✅ Credit spreads correctly ALLOWED in very high IV (85%)
✅ Iron condors correctly FORBIDDEN in very low IV (15%)
✅ Long puts correctly ALLOWED in very low IV (15%)
✅ McMillan rule lookup: WORKING
✅ TastyTrade rule lookup: WORKING
✅ Trade approval logic: WORKING

🚀 RAG knowledge is ready for live trading integration!
```

### Key Test Scenarios

1. **Scenario: High IV (85%) - Long Call**
   - Result: ❌ REJECTED
   - Reason: "Strategy long_call is FORBIDDEN in very_high IV regime"

2. **Scenario: High IV (65%) - Iron Condor**
   - Result: ✅ APPROVED (80% confidence)
   - Reason: "Strategy matches IV regime; DTE in optimal range"

3. **Scenario: Low IV (15%) - Long Put**
   - Result: ✅ APPROVED
   - Reason: "Strategy allowed in very_low IV regime"

4. **Scenario: Low IV (15%) - Iron Condor**
   - Result: ❌ REJECTED
   - Reason: "Strategy iron_condor is FORBIDDEN in very_low IV regime"

## Trade Approval Algorithm

```python
approval_score = 0.0

# IV regime alignment (most important - 40%)
if strategy in allowed_strategies:
    approval_score += 0.4

# Strategy recommendation match (30%)
if strategy == recommended_strategy:
    approval_score += 0.3

# DTE alignment (20%)
if 30 <= dte <= 45:
    approval_score += 0.2

# McMillan guidance available (10%)
if has_mcmillan_guidance:
    approval_score += 0.1

# Decision
approved = approval_score >= 0.5  # 50% threshold
```

## Usage Examples

### Example 1: Full Validation
```python
from src.trading.rag_trade_advisor import RAGTradeAdvisor

advisor = RAGTradeAdvisor()

# Get comprehensive trade advice
advice = advisor.get_trade_advice(
    ticker="SPY",
    strategy="iron_condor",
    iv_rank=65,
    sentiment="neutral",
    dte=35,
    stock_price=450.0,
    current_iv=0.18
)

print(f"Approved: {advice['approved']}")
print(f"Confidence: {advice['confidence']:.1%}")
print(f"Recommendation: {advice['recommendation']}")
print(f"IV Regime: {advice['iv_regime']['regime']}")
print(f"McMillan: {advice['mcmillan_guidance'][:100]}...")
print(f"TastyTrade: {advice['tastytrade_guidance'][:100]}...")
```

### Example 2: Quick Strategy Validation
```python
# Just check if strategy is allowed in current IV regime
is_valid, details = advisor.validate_strategy_vs_iv("long_call", iv_rank=85)

if not is_valid:
    print(f"⚠️ Trade rejected: {details['rejection_reason']}")
```

### Example 3: Get Specific Rules
```python
# Get McMillan's rules for covered calls
rule = advisor.get_mcmillan_rule("covered_call")
print(rule)

# Get TastyTrade rules for iron condors
rule = advisor.get_tastytrade_rule("iron_condor", dte=35, iv_rank=60)
print(rule)
```

### Example 4: ExecutionAgent with RAG
```python
from src.agents.execution_agent import ExecutionAgent

# ExecutionAgent automatically uses RAG validation
agent = ExecutionAgent(
    alpaca_api=api,
    options_client=options_client,
    enable_rag_validation=True  # Default
)

# Execute with RAG validation
result = agent.execute_option_trade(
    option_symbol="SPY250117C00450000",
    side="sell_to_open",
    qty=1,
    order_type="limit",
    limit_price=2.50,
    # RAG parameters
    ticker="SPY",
    strategy="iron_condor",
    iv_rank=65,
    sentiment="neutral",
    dte=30,
    stock_price=450.0,
    current_iv=0.18
)

if result.get("status") == "REJECTED_BY_RAG":
    print(f"RAG blocked trade: {result['rejection_reason']}")
else:
    print(f"Trade executed: {result['status']}")
    print(f"RAG validation: {result.get('rag_validation', {})}")
```

## Trade Attribution

Every trade now includes RAG metadata for analysis:

```python
{
    "status": "SUBMITTED",
    "order_id": "abc123",
    "rag_validation": {
        "approved": true,
        "confidence": 0.8,
        "iv_regime": "high",
        "mcmillan_consulted": true,
        "tastytrade_consulted": true
    }
}
```

This enables:
- Post-trade analysis: "Did RAG-validated trades perform better?"
- Attribution: "Which knowledge source influenced this trade?"
- Learning: "Where did RAG warnings prove correct?"

## Implementation Files

1. **Core Advisor**: `src/trading/rag_trade_advisor.py` (485 lines)
2. **Execution Integration**: `src/agents/execution_agent.py` (modified)
3. **Planner Integration**: `src/analytics/options_profit_planner.py` (modified)
4. **Test Suite**: `tests/test_rag_trade_advisor.py` (190 lines)
5. **Standalone Test**: `scripts/test_rag_integration.py` (385 lines)
6. **Documentation**: `docs/RAG_TRADING_INTEGRATION.md` (this file)

## Benefits

### 1. Prevents Costly Mistakes
- ❌ **Before**: Buy puts when "overbought" regardless of IV → IV crush losses
- ✅ **After**: RAG rejects long puts in high IV, suggests credit spreads instead

### 2. Expert Validation
- Every trade validated against 34 chunks of expert knowledge
- McMillan's 40+ years of options expertise
- TastyTrade's data-driven research findings

### 3. Auditability
- Every trade decision includes RAG reasoning
- Can trace why trade was approved/rejected
- Supports post-mortem analysis

### 4. Continuous Learning
- RAG knowledge base can be expanded
- New books/research automatically integrated
- System gets smarter without code changes

## Future Enhancements

### Phase 2: Real-time RAG Updates
- Query live market data (VIX, skew, term structure)
- Dynamic IV regime adjustment based on market conditions
- Cross-reference with recent market events

### Phase 3: RAG-Driven Strategy Selection
- Instead of hardcoded strategies, ask RAG: "What's best for current conditions?"
- Multi-book consensus: McMillan + TastyTrade + Natenberg + Sheldon
- Generate custom strategies based on unique market conditions

### Phase 4: Performance Feedback Loop
- Track which RAG recommendations performed best
- Weight knowledge sources by historical accuracy
- Self-improving RAG through reinforcement learning

## Monitoring

### RAG Rejection Rate
Monitor how often RAG rejects trades:
- **Healthy**: 10-20% rejection rate (catching bad trades)
- **Too high**: 50%+ (overly conservative, missing opportunities)
- **Too low**: <5% (not filtering enough)

### Confidence Distribution
Track approval confidence scores:
- **Strong**: >70% confidence (clear match with knowledge)
- **Moderate**: 50-70% confidence (acceptable with caution)
- **Weak**: <50% confidence (rejected or requires override)

### Knowledge Source Usage
Which sources are most referenced:
- McMillan: Stop-loss rules, greeks guidance
- TastyTrade: Entry/exit timing, position sizing
- Both: Strategy selection, IV regime validation

## Rollback Plan

If RAG validation causes issues:

```python
# Disable RAG validation globally
execution_agent = ExecutionAgent(
    alpaca_api=api,
    enable_rag_validation=False  # Disable RAG
)

# Or disable for specific trade
# (RAG validation only triggers if ticker, strategy, iv_rank provided)
result = agent.execute_option_trade(
    option_symbol="SPY250117C00450000",
    side="sell_to_open",
    qty=1,
    # Don't pass RAG parameters → RAG skipped
)
```

## Conclusion

✅ **RAG knowledge successfully integrated into live trading**

**Before RAG**:
- Trade decisions based purely on signals
- No validation against expert knowledge
- Risk of strategy hallucination (wrong strategy for IV regime)
- No cross-check of sentiment vs expected move

**After RAG**:
- Every trade validated against McMillan + TastyTrade
- IV regime enforces correct strategy selection
- Expected move cross-check prevents overbought/oversold traps
- Confidence scoring with detailed reasoning
- Full auditability and attribution

**Result**: Smarter, safer options trading backed by 40+ years of expert knowledge.

---

**Next Steps**:
1. Monitor RAG rejection rate in live trading
2. Analyze performance: RAG-approved vs RAG-rejected trades
3. Expand knowledge base with additional books/research
4. Implement real-time market data integration
