# McMillan Options Knowledge Base - README

## Overview

A comprehensive, production-ready options trading knowledge base based on Lawrence G. McMillan's "Options as a Strategic Investment" (5th Edition). This system provides AI-queryable options expertise for strategy selection, risk management, position sizing, and trade validation.

**Created**: December 2, 2025
**Status**: ✅ Production Ready
**Total Code**: 2,701 lines
**Size**: 94 KB

---

## 🎯 What Problem Does This Solve?

Options trading requires deep knowledge of:
- **Greeks** (Delta, Gamma, Theta, Vega, Rho)
- **Strategy selection** based on market conditions
- **Risk management** and position sizing
- **IV-based decision making**
- **Entry and exit rules** for each strategy

Without this knowledge, traders:
- Choose wrong strategies for current IV environment
- Size positions incorrectly (too big = blowup, too small = no gains)
- Exit too early or too late
- Miss risk management protocols
- Violate tax rules unknowingly

**Solution**: This knowledge base provides instant access to McMillan's proven frameworks, making expert-level options decisions accessible to algorithms and humans alike.

---

## 📦 What's Included

### 1. Core Knowledge Base (930 lines)
**File**: `/home/user/trading/src/rag/collectors/mcmillan_options_collector.py`

**Contains**:
- ✅ Complete Greek definitions and guidance (5 Greeks)
- ✅ Strategy rulesets (5 strategies with full entry/exit/risk rules)
- ✅ IV-based decision framework (4 volatility bands)
- ✅ Expected move calculator (McMillan formula)
- ✅ Position sizing formulas
- ✅ Risk management protocols
- ✅ Tax trap awareness
- ✅ Assignment risk protocols

### 2. Integration Guide (540 lines)
**File**: `/home/user/trading/docs/mcmillan_options_integration.md`

**Contains**:
- Complete API reference for all methods
- 4 integration use cases with code examples
- RAG system ingestion guide
- Best practices and workflows
- Formula explanations
- Future enhancement roadmap

### 3. Practical Example (419 lines)
**File**: `/home/user/trading/examples/mcmillan_options_strategy_example.py`

**Contains**:
- Complete working strategy using knowledge base
- IV environment analysis
- Expected move calculation
- Strategy selection logic
- Trade setup generation
- Position sizing
- Risk management checklist
- 3 real-world examples (NVDA, AAPL, MSFT)

### 4. Complete Summary (437 lines)
**File**: `/home/user/trading/docs/MCMILLAN_OPTIONS_SUMMARY.md`

**Contains**:
- Overview of entire system
- File inventory
- Knowledge base contents
- Example outputs
- Integration patterns
- Performance metrics
- Next steps

### 5. Quick Reference (375 lines)
**File**: `/home/user/trading/docs/MCMILLAN_QUICK_REFERENCE.md`

**Contains**:
- One-page cheat sheet
- Core formulas
- Greek summaries
- IV decision matrix
- Strategy quick reference
- Risk rules
- Common mistakes
- Decision trees

---

## 🚀 Quick Start

### Basic Usage

```python
from src.rag.collectors.mcmillan_options_collector import McMillanOptionsKnowledgeBase

# Initialize
kb = McMillanOptionsKnowledgeBase()

# Get IV recommendation
rec = kb.get_iv_recommendation(iv_rank=65, iv_percentile=70)
print(rec['recommendation'])
# Output: "STRONGLY SELL PREMIUM"

# Calculate expected move
move = kb.calculate_expected_move(
    stock_price=150.0,
    implied_volatility=0.25,  # 25% IV
    days_to_expiration=30
)
print(f"Expected range: ${move['lower_bound']} - ${move['upper_bound']}")
# Output: "Expected range: $139.24 - $160.76"

# Get strategy rules
rules = kb.get_strategy_rules("iron_condor")
print(rules['market_outlook'])
# Output: "Neutral. Expect stock to stay range-bound."

# Position sizing
sizing = kb.get_position_size(
    portfolio_value=10000,
    option_premium=2.50
)
print(f"Max contracts: {sizing['max_contracts']}")
# Output: "Max contracts: 0" (need cheaper options or bigger portfolio)
```

### Run Examples

```bash
# Test core knowledge base
python3 /home/user/trading/src/rag/collectors/mcmillan_options_collector.py

# Run practical strategy example
python3 /home/user/trading/examples/mcmillan_options_strategy_example.py
```

---

## 📚 Core Capabilities

### 1. Greek Analysis

Get comprehensive guidance for any Greek:

```python
delta = kb.get_greek_guidance("delta")
print(delta['trading_implications'])
# "High delta (>0.70): Behaves like stock, less time decay.
#  Low delta (<0.30): Cheaper, more leverage, faster decay.
#  ATM delta (~0.50): Balanced risk/reward for directional plays."
```

**Available Greeks**: delta, gamma, theta, vega, rho

### 2. Expected Move Calculator

Calculate expected price range using McMillan's formula:

```python
move = kb.calculate_expected_move(
    stock_price=100.0,
    implied_volatility=0.30,  # 30% IV
    days_to_expiration=30,
    confidence_level=1.0  # 1σ = 68% probability
)

# Returns:
{
    "expected_move": 8.60,
    "upper_bound": 108.60,
    "lower_bound": 91.40,
    "probability": 0.68,
    "formula": "100 × 0.30 × √(30/365) × 1.0"
}
```

**Formula**: `Expected Move = Stock Price × IV × √(DTE/365)`

### 3. IV-Based Recommendations

Get buy/sell recommendations based on IV environment:

```python
rec = kb.get_iv_recommendation(iv_rank=68, iv_percentile=72)

# Returns:
{
    "recommendation": "STRONGLY SELL PREMIUM",
    "reasoning": "IV is very high. Options are expensive. Mean reversion edge...",
    "strategies": ["iron_condor", "straddle_short", "strangle_short"],
    "confidence": "high"
}
```

**Decision Matrix**:
- **IV Rank 0-20%**: BUY PREMIUM (long calls/puts)
- **IV Rank 20-40%**: NEUTRAL (case by case)
- **IV Rank 40-60%**: FAVOR SELLING (iron condor, covered call)
- **IV Rank 60-100%**: STRONGLY SELL (iron condor, credit spreads)

### 4. Strategy Rules

Get complete rulesets for any strategy:

```python
rules = kb.get_strategy_rules("iron_condor")

# Returns:
{
    "strategy_name": "Iron Condor",
    "description": "Sell OTM call spread + OTM put spread...",
    "market_outlook": "Neutral. Expect stock to stay range-bound.",
    "setup_rules": [
        "Sell OTM put, buy further OTM put (bull put spread)",
        "Sell OTM call, buy further OTM call (bear call spread)",
        ...
    ],
    "entry_criteria": [...],
    "exit_rules": [...],
    "risk_management": [...],
    "optimal_conditions": {
        "iv_rank_min": 50,
        "dte_min": 30,
        "dte_max": 45
    }
}
```

**Available Strategies**:
- covered_call
- iron_condor
- cash_secured_put
- long_call
- protective_put

### 5. Position Sizing

Calculate safe position size within risk limits:

```python
sizing = kb.get_position_size(
    portfolio_value=10000,
    option_premium=2.50,
    max_risk_pct=0.02  # 2% max risk
)

# Returns:
{
    "max_contracts": 0,  # Can't afford within 2% risk limit
    "max_risk_dollars": 200.0,
    "cost_per_contract": 250.0,
    "total_cost": 0.0,
    "risk_percentage": 0.0,
    "recommendation": "Need premium ≤ $2.00 to trade 1 contract"
}
```

### 6. Risk Management

Get comprehensive risk rules:

```python
risk = kb.get_risk_rules("stop_losses")

# Returns:
{
    "long_options": {
        "max_loss": 0.50,  # Exit at 50% loss
        "trailing_stop": 0.25
    },
    "short_options": {
        "max_loss": 2.0,  # Exit if down 2x credit received
        "mechanical_stop": True
    },
    ...
}
```

**Risk Categories**:
- position_sizing
- stop_losses
- tax_traps
- assignment_risk

---

## 🎓 Knowledge Base Contents

### The Greeks (5 Complete Guides)

Each Greek includes:
- Definition and mathematical meaning
- Range and interpretation
- Trading implications
- Peak conditions
- Practical examples

**Example - Theta**:
- **Definition**: Rate of time decay - daily option value loss
- **Range**: Negative for long options
- **Interpretation**: Theta measures daily decay. -$0.05 theta = lose $5/day per contract
- **Trading Implications**: Sell options to collect theta. Optimal 30-45 DTE.
- **Peak Conditions**: Decay accelerates exponentially in final 30 days

### Strategy Rulesets (5 Complete Strategies)

Each strategy includes:
- Market outlook and use case
- Setup rules (strikes, DTE, etc.)
- Entry criteria (IV, technical, etc.)
- Position sizing guidelines
- Exit rules (profit targets, stops)
- Risk management protocols
- Common mistakes to avoid
- Optimal conditions (IV, DTE, delta)

**Example - Iron Condor**:
```
Market Outlook: Neutral, range-bound
Setup: Short strikes at 1σ, wings 5-10 wide
Entry: IV Rank > 50%, 30-45 DTE
Exit: 50% profit or tested side
Risk: Spread width - credit received
Optimal: IV Rank > 50%, 30-45 DTE, 16 delta strikes
```

### Volatility Framework (4 IV Bands)

Each band provides:
- IV Rank range
- IV Percentile range
- Buy/sell recommendation
- Reasoning
- Suggested strategies
- Confidence level

**Example - High IV (60-100%)**:
```
Recommendation: STRONGLY SELL PREMIUM
Reasoning: IV very high, expensive options, strong mean reversion edge
Strategies: iron_condor, straddle_short, strangle_short, credit_spread
```

### Risk Management (4 Categories)

**Position Sizing**:
- Max 2% risk per trade
- Max 10% in single position
- Max 30% in options total
- Scaling rules (50% → 25% → 25%)

**Stop Losses**:
- Long options: 50% loss or 25% trailing
- Short options: 2x credit received
- Stock: 8% below entry

**Tax Traps**:
- Wash sale rule (30 days)
- Straddle rules
- Qualified covered calls

**Assignment Risk**:
- Early assignment triggers
- Prevention strategies
- Ex-dividend awareness

---

## 💡 Integration Use Cases

### Use Case 1: Pre-Trade Validation

Validate every options trade before execution:

```python
def validate_trade(ticker, strategy, iv_rank, dte):
    kb = McMillanOptionsKnowledgeBase()

    # Get strategy rules
    rules = kb.get_strategy_rules(strategy)

    # Check IV matches strategy
    iv_rec = kb.get_iv_recommendation(iv_rank, iv_rank)
    if strategy not in iv_rec['strategies']:
        return False, f"IV Rank {iv_rank}% not optimal for {strategy}"

    # Check DTE in range
    optimal_dte_min = rules['optimal_conditions']['dte_min']
    if dte < optimal_dte_min:
        return False, f"DTE {dte} below optimal {optimal_dte_min}"

    return True, "Trade validated"
```

### Use Case 2: Strike Selection

Use expected move to select strikes:

```python
def select_iron_condor_strikes(stock_price, iv, dte):
    kb = McMillanOptionsKnowledgeBase()

    # Get 1 std dev move
    move = kb.calculate_expected_move(stock_price, iv, dte, 1.0)

    # Short strikes at 1σ
    short_put = move['lower_bound']
    short_call = move['upper_bound']

    # Wings 5-10 strikes wide
    wing_width = 5 if stock_price < 100 else 10
    long_put = short_put - wing_width
    long_call = short_call + wing_width

    return {
        "short_put": short_put,
        "long_put": long_put,
        "short_call": short_call,
        "long_call": long_call
    }
```

### Use Case 3: RAG Integration

Ingest knowledge into vector database for natural language queries:

```python
def ingest_to_rag():
    kb = McMillanOptionsKnowledgeBase()
    knowledge = kb.get_all_knowledge()

    # Extract documents for vector DB
    documents = []

    # Add Greeks
    for name, greek in knowledge['greeks'].items():
        doc = {
            "content": f"{greek['name']}: {greek['definition']}...",
            "metadata": {"type": "greek", "name": name}
        }
        documents.append(doc)

    # Add strategies, volatility guidance, etc.
    # ... (see integration guide for full code)

    # Embed and store in Chroma/Pinecone/etc.
    return documents
```

### Use Case 4: Automated Strategy Selection

Let system auto-select optimal strategy:

```python
def auto_select_strategy(iv_rank, dte):
    kb = McMillanOptionsKnowledgeBase()

    # Get IV recommendation
    rec = kb.get_iv_recommendation(iv_rank, iv_rank)

    # Select best strategy based on DTE
    if "SELL PREMIUM" in rec['recommendation']:
        return "iron_condor" if dte >= 30 else "covered_call"
    elif "BUY PREMIUM" in rec['recommendation']:
        return "long_call"
    else:
        return "cash_secured_put"
```

---

## 🧪 Testing & Validation

### Test Core Knowledge Base

```bash
python3 /home/user/trading/src/rag/collectors/mcmillan_options_collector.py
```

**Expected Output**:
```
================================================================================
MCMILLAN OPTIONS KNOWLEDGE BASE - EXAMPLES
================================================================================

1. DELTA GUIDANCE:
Definition: Rate of change of option price with respect to underlying price
Trading Implications: High delta (>0.70): Behaves like stock...

2. EXPECTED MOVE CALCULATION:
Stock: $8.6 expected move
Range: $91.4 - $108.6 (68.0% probability)

3. IRON CONDOR STRATEGY:
Description: Sell OTM call spread + OTM put spread...
Setup Rules:
  - Sell OTM put, buy further OTM put (bull put spread)
  - Sell OTM call, buy further OTM call (bear call spread)
  ...

4. IV RECOMMENDATION:
Recommendation: STRONGLY SELL PREMIUM
Reasoning: IV is very high. Options are expensive...

5. POSITION SIZING:
Max Contracts: 0
Total Cost: $0.0
Risk: 0.0%
```

### Test Strategy Example

```bash
python3 /home/user/trading/examples/mcmillan_options_strategy_example.py
```

**Expected Output**:
```
EXAMPLE 1: High IV Environment - Sell Premium Opportunity
Stock: NVDA @ $485.50
IV: 45% | IV Rank: 68% | DTE: 35

✓ RECOMMENDATION: STRONGLY SELL PREMIUM
✓ STRATEGY SELECTED: Iron Condor
✓ EXPECTED MOVE: $67.65 (1σ) | Range: $417.85 - $553.15
✓ RESULT: TRADE APPROVED (All checks passed)
```

---

## 📖 Documentation Index

### Quick Reference (Start Here)
- **[MCMILLAN_QUICK_REFERENCE.md](MCMILLAN_QUICK_REFERENCE.md)** - One-page cheat sheet

### Core Documentation
- **[mcmillan_options_integration.md](mcmillan_options_integration.md)** - Complete API reference and integration guide
- **[MCMILLAN_OPTIONS_SUMMARY.md](MCMILLAN_OPTIONS_SUMMARY.md)** - Comprehensive overview of entire system
- **[README_MCMILLAN_OPTIONS.md](README_MCMILLAN_OPTIONS.md)** - This file

### Code Files
- **[mcmillan_options_collector.py](/home/user/trading/src/rag/collectors/mcmillan_options_collector.py)** - Core knowledge base
- **[mcmillan_options_strategy_example.py](/home/user/trading/examples/mcmillan_options_strategy_example.py)** - Working example

---

## 🎯 Key Formulas

### Expected Move
```
1σ Move = Stock Price × IV × √(DTE/365)
2σ Move = 1σ Move × 2

Probabilities:
- 1σ = 68% probability
- 2σ = 95% probability
```

### Position Sizing
```
Max Risk = Portfolio Value × 2%
Max Contracts = Max Risk / (Premium × 100)
```

### IV Rank
```
IV Rank = (Current IV - 52wk Low) / (52wk High - 52wk Low) × 100
```

---

## ⚡ Performance Metrics

### Code Stats
- **Total Lines**: 2,701
- **Core KB**: 930 lines
- **Documentation**: 1,352 lines
- **Examples**: 419 lines
- **Total Size**: 94 KB

### Knowledge Coverage
- **Greeks**: 5 (complete guidance)
- **Strategies**: 5 (complete rulesets)
- **IV Bands**: 4 (with recommendations)
- **Risk Categories**: 4 (comprehensive protocols)

### Test Results
```
✅ All Greeks retrievable
✅ Expected move calculations accurate
✅ Strategy rules complete
✅ IV recommendations working
✅ Position sizing correct
✅ Risk protocols comprehensive
✅ Examples run successfully
✅ Integration tested
```

---

## 🔮 Future Enhancements

### Phase 1: Additional Strategies
- Butterfly spreads
- Calendar spreads
- Diagonal spreads
- Ratio spreads
- PMCC (Poor Man's Covered Call)

### Phase 2: Advanced Features
- Volatility skew analysis
- Earnings play strategies
- Roll decision trees
- Greeks calculator (real-time)
- Strategy comparison tool

### Phase 3: Integration
- Backtesting integration
- Live trade validation
- Performance tracking
- Strategy optimization
- Risk alerts

---

## 🤝 Contributing

To add new strategies or enhance existing knowledge:

1. **Add Strategy Rules**: Update `_initialize_strategies()` in `mcmillan_options_collector.py`
2. **Add Greek Guidance**: Update `_initialize_greeks()` for new insights
3. **Add Risk Rules**: Update `_initialize_risk_rules()` for new protocols
4. **Test**: Run test suite to validate changes
5. **Document**: Update integration guide and quick reference

---

## 📚 References

**Primary Source**:
- **Book**: "Options as a Strategic Investment"
- **Author**: Lawrence G. McMillan
- **Edition**: 5th Edition
- **Publisher**: Penguin Publishing Group
- **ISBN**: 978-0735204652
- **Pages**: 1,100+

**Knowledge Extracted**:
- Complete Greeks framework
- Strategy construction and management
- Volatility trading principles
- Risk management protocols
- Tax and assignment considerations

---

## 🆘 Support

### Common Issues

**Q: Position sizing returns 0 contracts**
A: Premium too expensive for 2% risk limit. Need cheaper options or bigger portfolio.

**Q: Strategy not found**
A: Use underscores (e.g., `iron_condor` not `iron condor`). Check `list_strategies()` for available strategies.

**Q: Import error**
A: Use direct import if dependencies missing:
```python
import importlib.util
spec = importlib.util.spec_from_file_location(
    "mcmillan",
    "/home/user/trading/src/rag/collectors/mcmillan_options_collector.py"
)
kb_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kb_module)
kb = kb_module.McMillanOptionsKnowledgeBase()
```

### Getting Help

1. Check [MCMILLAN_QUICK_REFERENCE.md](MCMILLAN_QUICK_REFERENCE.md) for quick answers
2. Review [mcmillan_options_integration.md](mcmillan_options_integration.md) for detailed API docs
3. Run examples to see working code
4. Review McMillan's book for deeper understanding

---

## ✅ Quick Checklist

Before using this system in production:

- [ ] Understand the Greeks (read Greek guidance)
- [ ] Know IV decision matrix (memorize 4 bands)
- [ ] Learn position sizing formula (2% max risk)
- [ ] Review strategy rules (read all 5 rulesets)
- [ ] Test with paper trading first
- [ ] Validate all trades before execution
- [ ] Set up risk management alerts
- [ ] Review tax implications

---

## 🎓 Learning Path

### Beginner (Week 1)
1. Read [MCMILLAN_QUICK_REFERENCE.md](MCMILLAN_QUICK_REFERENCE.md)
2. Learn The Greeks (delta, gamma, theta)
3. Understand IV decision matrix
4. Practice expected move calculations

### Intermediate (Week 2-3)
1. Study all 5 strategy rulesets
2. Practice strike selection
3. Learn position sizing
4. Review risk management protocols

### Advanced (Week 4+)
1. Build automated strategy selector
2. Integrate with RAG system
3. Backtest strategies
4. Optimize for your portfolio

---

## 📊 Quick Decision Matrix

```
IF IV Rank > 60% THEN
    Strategy = Iron Condor or Credit Spread
    DTE = 30-45
    Action = SELL PREMIUM

ELSE IF IV Rank < 30% THEN
    Strategy = Long Call or Long Put
    DTE = 60-90
    Action = BUY PREMIUM

ELSE
    Strategy = Case by case
    DTE = Based on strategy
    Action = NEUTRAL
```

---

## 🏆 Success Metrics

Track these metrics to measure effectiveness:

- **Win Rate**: >60% for credit strategies
- **Sharpe Ratio**: >1.5 for options portfolio
- **Max Drawdown**: <10% of portfolio
- **Avg Return**: 3-5% monthly for credit strategies
- **Risk Compliance**: 100% trades within 2% risk limit

---

**Created**: December 2, 2025
**Author**: Claude (AI Agent)
**Knowledge Source**: Lawrence G. McMillan - "Options as a Strategic Investment"
**Version**: 1.0
**Status**: ✅ Production Ready

---

**Ready to trade smarter? Start with the [Quick Reference](MCMILLAN_QUICK_REFERENCE.md)!**
