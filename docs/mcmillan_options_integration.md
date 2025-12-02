# McMillan Options Knowledge Base - Integration Guide

## Overview

The McMillan Options Knowledge Base (`mcmillan_options_collector.py`) provides comprehensive options trading knowledge from Lawrence G. McMillan's "Options as a Strategic Investment" (5th Edition).

**Location**: `/home/user/trading/src/rag/collectors/mcmillan_options_collector.py`

## Core Capabilities

### 1. Greek Analysis
- **Delta**: Directional exposure and probability of ITM
- **Gamma**: Delta change rate and risk acceleration
- **Theta**: Time decay and optimal selling windows
- **Vega**: IV sensitivity and volatility trading
- **Rho**: Interest rate sensitivity for LEAPS

### 2. Strategy Rules
Complete rulesets for:
- Covered Call
- Iron Condor
- Cash-Secured Put
- Long Call
- Protective Put

### 3. Expected Move Calculator
Calculate expected price ranges using:
```
Expected Move = Stock Price × IV × √(DTE/365)
```

### 4. IV-Based Recommendations
Get buy/sell recommendations based on:
- IV Rank (0-100)
- IV Percentile (0-100)

### 5. Risk Management
- Position sizing formulas
- Stop loss rules
- Tax trap awareness
- Assignment risk protocols

---

## Quick Start

```python
from src.rag.collectors.mcmillan_options_collector import McMillanOptionsKnowledgeBase

# Initialize knowledge base
kb = McMillanOptionsKnowledgeBase()

# Get Greek guidance
delta_info = kb.get_greek_guidance("delta")
print(delta_info['trading_implications'])

# Calculate expected move
move = kb.calculate_expected_move(
    stock_price=150.0,
    implied_volatility=0.25,  # 25% IV
    days_to_expiration=30,
    confidence_level=1.0  # 1 std dev = 68% probability
)
print(f"Expected range: ${move['lower_bound']} - ${move['upper_bound']}")

# Get strategy rules
iron_condor = kb.get_strategy_rules("iron_condor")
print(f"Setup rules: {iron_condor['setup_rules']}")

# Get IV recommendation
iv_rec = kb.get_iv_recommendation(iv_rank=65, iv_percentile=70)
print(f"Recommendation: {iv_rec['recommendation']}")

# Position sizing
sizing = kb.get_position_size(
    portfolio_value=10000,
    option_premium=3.50,  # $350 per contract
    max_risk_pct=0.02  # 2% max risk
)
print(f"Max contracts: {sizing['max_contracts']}")
```

---

## Integration with Trading System

### Use Case 1: Pre-Trade Validation

```python
from src.rag.collectors.mcmillan_options_collector import McMillanOptionsKnowledgeBase

def validate_options_trade(ticker, strategy, iv_rank, portfolio_value):
    """Validate options trade using McMillan knowledge base."""
    kb = McMillanOptionsKnowledgeBase()

    # Get strategy rules
    rules = kb.get_strategy_rules(strategy)
    if not rules:
        return {"valid": False, "reason": "Unknown strategy"}

    # Check IV conditions
    optimal_iv = rules['optimal_conditions'].get('iv_rank_min', 0)
    if iv_rank < optimal_iv:
        return {
            "valid": False,
            "reason": f"IV Rank {iv_rank} below optimal {optimal_iv} for {strategy}"
        }

    # Get IV recommendation
    iv_rec = kb.get_iv_recommendation(iv_rank=iv_rank, iv_percentile=iv_rank)

    # Validate strategy matches IV recommendation
    if strategy not in iv_rec['strategies']:
        return {
            "valid": False,
            "reason": f"Strategy {strategy} not recommended at IV Rank {iv_rank}",
            "recommendation": iv_rec['recommendation']
        }

    return {
        "valid": True,
        "rules": rules,
        "iv_recommendation": iv_rec
    }

# Example usage
result = validate_options_trade(
    ticker="AAPL",
    strategy="iron_condor",
    iv_rank=65,
    portfolio_value=10000
)
print(result)
```

### Use Case 2: Expected Move for Strike Selection

```python
def select_strikes_for_iron_condor(stock_price, iv, dte):
    """Select strikes using expected move calculation."""
    kb = McMillanOptionsKnowledgeBase()

    # Calculate 1 std dev move
    move = kb.calculate_expected_move(
        stock_price=stock_price,
        implied_volatility=iv,
        days_to_expiration=dte,
        confidence_level=1.0  # 1 std dev
    )

    # Place short strikes at 1 std dev
    short_put_strike = move['lower_bound']
    short_call_strike = move['upper_bound']

    # Wings 5-10 points wide (per McMillan)
    wing_width = 5 if stock_price < 100 else 10
    long_put_strike = short_put_strike - wing_width
    long_call_strike = short_call_strike + wing_width

    return {
        "short_put": round(short_put_strike, 2),
        "long_put": round(long_put_strike, 2),
        "short_call": round(short_call_strike, 2),
        "long_call": round(long_call_strike, 2),
        "expected_move": move
    }

# Example
strikes = select_strikes_for_iron_condor(
    stock_price=150.0,
    iv=0.30,  # 30% IV
    dte=30
)
print(f"Iron Condor Strikes: {strikes}")
```

### Use Case 3: Dynamic Position Sizing

```python
def calculate_trade_size(portfolio_value, strategy, option_premium, iv_rank):
    """Calculate position size with risk management."""
    kb = McMillanOptionsKnowledgeBase()

    # Get strategy rules
    rules = kb.get_strategy_rules(strategy)

    # Adjust risk based on IV
    if iv_rank > 70:
        # High IV = higher risk, reduce size
        max_risk_pct = 0.015  # 1.5%
    elif iv_rank < 30:
        # Low IV = lower risk, can size up slightly
        max_risk_pct = 0.025  # 2.5%
    else:
        # Normal conditions
        max_risk_pct = 0.02  # 2%

    # Calculate position size
    sizing = kb.get_position_size(
        portfolio_value=portfolio_value,
        option_premium=option_premium,
        max_risk_pct=max_risk_pct
    )

    return {
        "contracts": sizing['max_contracts'],
        "cost": sizing['total_cost'],
        "risk_pct": sizing['risk_percentage'],
        "reasoning": f"IV Rank {iv_rank} → {max_risk_pct*100}% risk limit"
    }
```

### Use Case 4: RAG System Integration

```python
def ingest_mcmillan_knowledge_to_rag():
    """Ingest McMillan knowledge into RAG vector database."""
    from src.rag.collectors.mcmillan_options_collector import McMillanOptionsKnowledgeBase
    from src.rag.vector_db.chroma_client import ChromaClient
    from src.rag.vector_db.embedder import Embedder

    kb = McMillanOptionsKnowledgeBase()
    chroma = ChromaClient()
    embedder = Embedder()

    # Export all knowledge
    knowledge = kb.get_all_knowledge()

    # Prepare documents for ingestion
    documents = []

    # Add Greeks
    for greek_name, greek_data in knowledge['greeks'].items():
        doc = {
            "content": (
                f"{greek_data['name']}: {greek_data['definition']}. "
                f"{greek_data['interpretation']} "
                f"Trading implications: {greek_data['trading_implications']}"
            ),
            "metadata": {
                "type": "greek",
                "name": greek_name,
                "source": "McMillan Options"
            }
        }
        documents.append(doc)

    # Add Strategies
    for strategy_name, strategy_data in knowledge['strategies'].items():
        doc = {
            "content": (
                f"{strategy_data['strategy_name']}: {strategy_data['description']}. "
                f"Market outlook: {strategy_data['market_outlook']}. "
                f"Setup: {', '.join(strategy_data['setup_rules'])}. "
                f"Entry: {', '.join(strategy_data['entry_criteria'])}."
            ),
            "metadata": {
                "type": "strategy",
                "name": strategy_name,
                "source": "McMillan Options"
            }
        }
        documents.append(doc)

    # Add Volatility Guidance
    for vol_guidance in knowledge['volatility_guidance']:
        doc = {
            "content": (
                f"IV Rank {vol_guidance['iv_rank_min']}-{vol_guidance['iv_rank_max']}: "
                f"{vol_guidance['recommendation']}. {vol_guidance['reasoning']} "
                f"Best strategies: {', '.join(vol_guidance['strategies'])}."
            ),
            "metadata": {
                "type": "volatility_guidance",
                "iv_range": f"{vol_guidance['iv_rank_min']}-{vol_guidance['iv_rank_max']}",
                "source": "McMillan Options"
            }
        }
        documents.append(doc)

    # Embed and store
    for doc in documents:
        embedding = embedder.embed(doc['content'])
        chroma.add_document(
            collection_name="options_knowledge",
            document_id=f"mcmillan_{doc['metadata']['type']}_{doc['metadata'].get('name', 'general')}",
            embedding=embedding,
            metadata=doc['metadata'],
            content=doc['content']
        )

    print(f"Ingested {len(documents)} McMillan knowledge entries to RAG")
    return len(documents)
```

---

## API Reference

### McMillanOptionsKnowledgeBase Methods

#### `get_greek_guidance(greek_name: str) -> Dict`
Get comprehensive guidance for a specific Greek.

**Parameters**:
- `greek_name`: One of 'delta', 'gamma', 'theta', 'vega', 'rho'

**Returns**:
```python
{
    "name": "Delta",
    "definition": "Rate of change...",
    "range": "0 to 1.0 for calls...",
    "interpretation": "Delta measures...",
    "trading_implications": "High delta...",
    "peak_conditions": "Delta is highest..."
}
```

#### `calculate_expected_move(stock_price, implied_volatility, days_to_expiration, confidence_level) -> Dict`
Calculate expected price range using McMillan's formula.

**Parameters**:
- `stock_price`: Current stock price (float)
- `implied_volatility`: IV as decimal (0.30 = 30%)
- `days_to_expiration`: Days until expiration (int)
- `confidence_level`: 1.0 = 1 std dev (68%), 2.0 = 2 std dev (95%)

**Returns**:
```python
{
    "expected_move": 8.6,
    "upper_bound": 108.6,
    "lower_bound": 91.4,
    "move_percentage": 8.6,
    "probability": 0.68,
    "confidence_level": 1.0,
    "annual_iv": 0.30,
    "dte": 30,
    "formula": "100 × 0.30 × √(30/365) × 1.0"
}
```

#### `get_strategy_rules(strategy_name: str) -> Dict`
Get complete ruleset for an options strategy.

**Parameters**:
- `strategy_name`: One of 'covered_call', 'iron_condor', 'cash_secured_put', 'long_call', 'protective_put'

**Returns**:
```python
{
    "strategy_name": "Iron Condor",
    "description": "Sell OTM call spread + OTM put spread...",
    "market_outlook": "Neutral. Expect stock to stay range-bound.",
    "setup_rules": [...],
    "entry_criteria": [...],
    "position_sizing": [...],
    "exit_rules": [...],
    "risk_management": [...],
    "common_mistakes": [...],
    "optimal_conditions": {
        "iv_rank_min": 50,
        "dte_min": 30,
        ...
    }
}
```

#### `get_iv_recommendation(iv_rank: float, iv_percentile: float) -> Dict`
Get trading recommendation based on IV metrics.

**Parameters**:
- `iv_rank`: IV Rank (0-100)
- `iv_percentile`: IV Percentile (0-100)

**Returns**:
```python
{
    "recommendation": "STRONGLY SELL PREMIUM",
    "reasoning": "IV is very high...",
    "strategies": ["iron_condor", "straddle_short", ...],
    "iv_rank": 65.0,
    "iv_percentile": 70.0,
    "confidence": "high",  # high/medium/low
    "note": None
}
```

#### `get_position_size(portfolio_value, option_premium, max_risk_pct) -> Dict`
Calculate optimal position size based on risk.

**Parameters**:
- `portfolio_value`: Total portfolio value (float)
- `option_premium`: Premium per contract in dollars (float)
- `max_risk_pct`: Max risk as decimal (default 0.02 = 2%)

**Returns**:
```python
{
    "max_contracts": 5,
    "max_risk_dollars": 200.0,
    "cost_per_contract": 250.0,
    "total_cost": 1250.0,
    "risk_percentage": 12.5,
    "recommendation": "Trade up to 5 contracts..."
}
```

#### `get_risk_rules(category: str = None) -> Dict`
Get risk management rules.

**Parameters**:
- `category`: Optional. One of 'position_sizing', 'stop_losses', 'tax_traps', 'assignment_risk'

**Returns**: Dictionary with risk rules for specified category or all rules if None.

#### `get_all_knowledge() -> Dict`
Export entire knowledge base as dictionary for RAG ingestion.

**Returns**: Complete knowledge base with Greeks, strategies, volatility guidance, and risk rules.

#### `search_knowledge(query: str) -> List[Dict]`
Search knowledge base for relevant information.

**Parameters**:
- `query`: Search query (e.g., "iron condor setup", "gamma risk")

**Returns**: List of relevant knowledge entries.

#### `list_strategies() -> List[str]`
Get list of all available strategies.

**Returns**: `['covered_call', 'iron_condor', 'cash_secured_put', 'long_call', 'protective_put']`

---

## Testing

Run the built-in examples:
```bash
python3 /home/user/trading/src/rag/collectors/mcmillan_options_collector.py
```

This will demonstrate:
1. Greek guidance retrieval
2. Expected move calculation
3. Strategy rules lookup
4. IV-based recommendations
5. Position sizing

---

## Key Formulas

### Expected Move
```
Expected Move (1σ) = Stock Price × IV × √(DTE/365)
Expected Move (2σ) = Expected Move (1σ) × 2
```

### Position Sizing
```
Max Contracts = (Portfolio Value × Max Risk %) / (Premium × 100)
```

### IV Rank
```
IV Rank = (Current IV - 52wk Low IV) / (52wk High IV - 52wk Low IV) × 100
```

### IV Percentile
```
IV Percentile = (Days IV was below current level / Total days) × 100
```

---

## Best Practices

### 1. Pre-Trade Checklist
- [ ] Verify strategy matches IV environment (use `get_iv_recommendation()`)
- [ ] Calculate expected move (use `calculate_expected_move()`)
- [ ] Size position appropriately (use `get_position_size()`)
- [ ] Review strategy rules (use `get_strategy_rules()`)
- [ ] Check risk management protocols (use `get_risk_rules()`)

### 2. IV Decision Framework
- **IV Rank > 50%**: Sell premium (iron condor, covered call, credit spreads)
- **IV Rank < 50%**: Buy premium (long calls/puts, debit spreads)
- **IV Rank 40-60%**: Neutral - case by case

### 3. Position Sizing Rules
- Never risk more than 2% per trade
- Scale into positions (50% → 25% → 25%)
- Adjust for IV (higher IV = smaller size)

### 4. Exit Discipline
- Take profit at 50% for credit spreads (best risk/reward)
- Stop loss at 50% for debit spreads
- Don't hold past 21 DTE unless deep ITM

---

## Future Enhancements

Potential additions to knowledge base:
1. Volatility skew analysis
2. Earnings play strategies
3. LEAPS strategies (diagonal spreads, PMCC)
4. Ratio spreads and backspreads
5. Butterfly and condor variations
6. Synthetic positions
7. Roll mechanics and decision trees
8. Tax optimization strategies

---

## References

- **Book**: "Options as a Strategic Investment" by Lawrence G. McMillan (5th Edition)
- **Author**: Lawrence G. McMillan
- **Publisher**: Penguin Publishing Group
- **ISBN**: 978-0735204652

---

## Support

For questions or issues with the knowledge base:
1. Review this documentation
2. Check the inline code documentation
3. Run the example usage: `python3 mcmillan_options_collector.py`
4. Review McMillan's book for deeper understanding

---

**Last Updated**: December 2, 2025
**Version**: 1.0
**Status**: Production Ready
