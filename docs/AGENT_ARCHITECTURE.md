# Trading System - Introspective Agent Architecture

**Version**: 1.0
**Date**: October 31, 2025
**Based on**: Anthropic's Introspection Research + Claude Agents SDK

---

## Overview

This document describes our multi-agent trading system architecture leveraging Claude's introspection capabilities for safer, more transparent, and more profitable trading decisions.

## Key Principles

### 1. Introspection-First Design
- Every agent can **question its own reasoning**
- Agents **detect biases** before they cause problems
- Agents **verify consistency** between data sources
- Agents **validate outputs** before execution

### 2. Multi-Agent Specialization
- **Research Agent**: Market analysis & sentiment
- **Signal Agent**: Entry/exit decision making
- **Risk Agent**: Position sizing & safety
- **Execution Agent**: Order management & verification

### 3. Defensive Decision Making
- Agents must pass **self-checks** before proceeding
- Multiple layers of **safety guardrails**
- Explicit **reason logging** for audit trail
- **Introspective debugging** built into workflows

---

## Agent Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  Master Trading Agent                         │
│                    (Orchestrator)                             │
│  • Coordinates subagents                                      │
│  • Aggregates decisions                                       │
│  • Final go/no-go authority                                   │
└─────────────────────────────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┬─────────────────┐
        │                 │                 │                 │
        ▼                 ▼                 ▼                 ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│   Research    │ │    Signal     │ │     Risk      │ │  Execution    │
│     Agent     │ │     Agent     │ │     Agent     │ │     Agent     │
├───────────────┤ ├───────────────┤ ├───────────────┤ ├───────────────┤
│ • News        │ │ • MACD        │ │ • Max loss    │ │ • Order       │
│ • Sentiment   │ │ • RSI         │ │ • Position    │ │   validation  │
│ • Macro data  │ │ • Volume      │ │   limits      │ │ • Alpaca API  │
│ • Reddit      │ │ • Momentum    │ │ • Circuit     │ │ • Pre-flight  │
│               │ │               │ │   breakers    │ │   checks      │
├───────────────┤ ├───────────────┤ ├───────────────┤ ├───────────────┤
│ INTROSPECTION │ │ INTROSPECTION │ │ INTROSPECTION │ │ INTROSPECTION │
├───────────────┤ ├───────────────┤ ├───────────────┤ ├───────────────┤
│ "Am I biased  │ │ "Do indicators│ │ "Is trade     │ │ "Does order   │
│  by news?"    │ │  agree?"      │ │  safe?"       │ │  match intent?"│
└───────────────┘ └───────────────┘ └───────────────┘ └───────────────┘
```

---

## Research Agent

### Purpose
Gather market context, sentiment, and macro data to inform trading decisions.

### Tools
- `webfetch`: Fetch financial news
- `alpha_vantage_api`: News sentiment scores
- `reddit_api`: Social sentiment (r/wallstreetbets, r/stocks)
- `fred_api`: Economic indicators (interest rates, employment)

### Introspection Capabilities

**Self-Check #1: Bias Detection**
```python
def check_sentiment_bias(self):
    """
    Agent questions: Am I being too influenced by recent news?

    Returns:
        bias_score: 0.0 (no bias) to 1.0 (extreme bias)
        recommendation: Continue or flag for review
    """
    news_sentiment = self.get_news_sentiment()
    technical_signal = self.get_technical_signal()
    social_sentiment = self.get_social_sentiment()

    # Introspect: Are all sources aligned?
    alignment = calculate_alignment([news_sentiment, technical_signal, social_sentiment])

    if alignment < 0.5:
        return {
            "warning": "High divergence between sources",
            "bias_detected": True,
            "recommendation": "Reduce confidence in signal"
        }

    return {"bias_detected": False}
```

**Self-Check #2: Data Quality**
```python
def validate_data_quality(self):
    """
    Agent questions: Is my data reliable and recent?
    """
    data_age = self.get_data_staleness()
    source_reliability = self.check_source_reputation()

    if data_age > 3600:  # More than 1 hour old
        return {"stale_data": True, "confidence_penalty": 0.3}

    if source_reliability < 0.7:
        return {"unreliable_source": True, "confidence_penalty": 0.5}

    return {"quality": "high"}
```

### Output
```json
{
  "market_sentiment": 0.65,
  "news_summary": "Positive tech earnings, Fed holds rates",
  "social_sentiment": 0.72,
  "macro_indicators": {"gdp_growth": 2.1, "unemployment": 3.8},
  "confidence": 0.85,
  "introspection": {
    "bias_detected": false,
    "data_quality": "high",
    "sources_aligned": true
  }
}
```

---

## Signal Agent

### Purpose
Generate buy/sell/hold signals based on technical indicators.

### Tools
- `calculate_macd`: MACD indicator
- `calculate_rsi`: RSI indicator
- `calculate_volume_ratio`: Volume analysis
- `calculate_momentum`: Multi-period momentum

### Introspection Capabilities

**Self-Check #1: Indicator Consensus**
```python
def check_indicator_consensus(self):
    """
    Agent questions: Do my indicators agree on the signal?
    """
    macd_signal = self.macd.get_signal()  # "BUY", "SELL", "HOLD"
    rsi_signal = self.rsi.get_signal()
    volume_signal = self.volume.get_signal()
    momentum_signal = self.momentum.get_signal()

    signals = [macd_signal, rsi_signal, volume_signal, momentum_signal]
    consensus = calculate_consensus(signals)

    if consensus < 0.75:  # Less than 75% agreement
        return {
            "warning": "Indicators disagree",
            "consensus": consensus,
            "recommendation": "Reduce position size or skip trade"
        }

    return {"consensus": consensus, "strong_signal": True}
```

**Self-Check #2: Overbought/Oversold Detection**
```python
def check_extreme_conditions(self):
    """
    Agent questions: Are we at an extreme that could reverse?
    """
    rsi = self.get_rsi()

    if rsi > 80:
        return {
            "warning": "Severely overbought (RSI > 80)",
            "recommendation": "Avoid BUY signals",
            "confidence_penalty": 0.5
        }

    if rsi < 20:
        return {
            "warning": "Severely oversold (RSI < 20)",
            "recommendation": "Avoid SELL signals",
            "confidence_penalty": 0.5
        }

    return {"conditions": "normal"}
```

### Output
```json
{
  "signal": "BUY",
  "confidence": 0.82,
  "indicators": {
    "macd": "bullish_crossover",
    "rsi": 58,
    "volume_ratio": 1.8,
    "momentum": 72
  },
  "introspection": {
    "indicator_consensus": 0.85,
    "extreme_conditions": false,
    "contradictions": []
  }
}
```

---

## Risk Agent

### Purpose
Validate trades against risk management rules and enforce safety limits.

### Tools
- `risk_manager`: Circuit breakers, position limits
- `calculate_position_size`: Kelly criterion, fixed fractional
- `check_circuit_breakers`: Daily loss limit, max drawdown
- `validate_stop_loss`: Stop-loss calculator

### Introspection Capabilities

**Self-Check #1: Risk Rule Compliance**
```python
def validate_risk_compliance(self, trade):
    """
    Agent questions: Does this trade violate any risk rules?
    """
    checks = {
        "within_daily_loss_limit": self.check_daily_loss(trade),
        "within_position_limit": self.check_position_size(trade),
        "below_max_drawdown": self.check_drawdown(),
        "consecutive_losses_ok": self.check_consecutive_losses(),
        "stop_loss_set": trade.stop_loss is not None
    }

    failed_checks = [k for k, v in checks.items() if not v]

    if failed_checks:
        return {
            "approved": False,
            "failed_checks": failed_checks,
            "reason": f"Trade violates: {', '.join(failed_checks)}"
        }

    return {"approved": True, "all_checks_passed": True}
```

**Self-Check #2: Position Sizing Sanity**
```python
def validate_position_size(self, trade):
    """
    Agent questions: Is this position size reasonable?
    """
    account_value = self.get_account_value()
    trade_value = trade.quantity * trade.price
    position_pct = (trade_value / account_value) * 100

    if position_pct > 20:  # Exceeds 20% of account
        return {
            "warning": f"Position is {position_pct:.1f}% of account",
            "recommendation": "Reduce position size",
            "approved": False
        }

    if position_pct < 0.1:  # Less than 0.1% of account
        return {
            "warning": "Position too small to be meaningful",
            "recommendation": "Increase size or skip trade",
            "approved": False
        }

    return {"approved": True, "position_pct": position_pct}
```

### Output
```json
{
  "approved": true,
  "position_size": 10.5,
  "risk_amount": 0.21,
  "stop_loss": 145.30,
  "risk_reward_ratio": 2.5,
  "introspection": {
    "all_risk_checks_passed": true,
    "position_size_reasonable": true,
    "circuit_breakers_inactive": true
  }
}
```

---

## Execution Agent

### Purpose
Execute trades via Alpaca API with final pre-flight checks.

### Tools
- `alpaca_trader`: Place orders, manage positions
- `validate_order`: Pre-flight order validation
- `check_market_hours`: Market open/close status

### Introspection Capabilities

**Self-Check #1: Order Correctness**
```python
def validate_order_correctness(self, order):
    """
    Agent questions: Does this order match the intended signal?
    """
    checks = {
        "symbol_correct": order.symbol in ALLOWED_SYMBOLS,
        "side_matches_signal": self.verify_side(order),
        "quantity_reasonable": self.verify_quantity(order),
        "stop_loss_set": order.stop_loss is not None,
        "market_is_open": self.check_market_hours()
    }

    failed = [k for k, v in checks.items() if not v]

    if failed:
        return {
            "execute": False,
            "reason": f"Pre-flight checks failed: {', '.join(failed)}"
        }

    return {"execute": True, "pre_flight_passed": True}
```

**Self-Check #2: Execution Intent Verification**
```python
def verify_execution_intent(self, signal, order):
    """
    Agent questions: Does my order truly reflect the trading signal?
    """
    intent_match = {
        "signal_buy_order_buy": signal == "BUY" and order.side == "buy",
        "signal_sell_order_sell": signal == "SELL" and order.side == "sell",
        "quantity_matches_risk": abs(order.quantity - signal.recommended_size) < 0.01,
        "stop_loss_matches": abs(order.stop_loss - signal.stop_loss) < 0.01
    }

    if not all(intent_match.values()):
        return {
            "warning": "Order does not match signal intent",
            "mismatches": [k for k, v in intent_match.items() if not v],
            "recommendation": "Review order before execution"
        }

    return {"intent_verified": True}
```

### Output
```json
{
  "order_placed": true,
  "order_id": "abc-123-def",
  "executed_at": "2025-10-31T10:35:00Z",
  "fill_price": 147.85,
  "introspection": {
    "pre_flight_passed": true,
    "intent_verified": true,
    "order_correctness": "confirmed"
  }
}
```

---

## Master Agent Orchestration

### Decision Flow

```python
async def execute_daily_trade():
    """
    Master agent coordinates all subagents with introspection at each step.
    """

    # Step 1: Research
    research = await research_agent.analyze_market()
    if research["introspection"]["bias_detected"]:
        logger.warning("Research agent detected bias - reducing confidence")
        research["confidence"] *= 0.7

    # Step 2: Signal Generation
    signal = await signal_agent.generate_signal(research)
    if signal["introspection"]["indicator_consensus"] < 0.75:
        logger.warning("Signal agent detected low consensus - skipping trade")
        return None

    # Step 3: Risk Validation
    risk_check = await risk_agent.validate_trade(signal)
    if not risk_check["approved"]:
        logger.error(f"Risk agent blocked trade: {risk_check['reason']}")
        return None

    # Step 4: Execution
    execution = await execution_agent.execute_order(signal, risk_check)
    if not execution["introspection"]["intent_verified"]:
        logger.error("Execution agent detected intent mismatch - aborting")
        return None

    # Step 5: Master Agent Final Review
    master_review = {
        "research_confidence": research["confidence"],
        "signal_confidence": signal["confidence"],
        "risk_approved": risk_check["approved"],
        "execution_verified": execution["introspection"]["intent_verified"]
    }

    if all(master_review.values()):
        logger.info("Master agent approves - trade executed successfully")
        return execution
    else:
        logger.error(f"Master agent review failed: {master_review}")
        return None
```

---

## Implementation Timeline

### Week 1 (Current - Nov 3)
- ✅ Document introspective agent architecture
- ✅ Update CLAUDE.md with R&D phase strategy
- 🔄 Update README with diagrams

### Week 2 (Nov 4-10)
- 🎯 Build Research Agent with introspection
- 🎯 Add Alpha Vantage + Reddit sentiment tools
- 🎯 Implement bias detection

### Week 3 (Nov 11-17)
- 🎯 Build Signal Agent with MACD + RSI + Volume
- 🎯 Add indicator consensus checks
- 🎯 Implement Risk Agent with circuit breakers

### Week 4 (Nov 18-24)
- 🎯 Build Execution Agent with pre-flight checks
- 🎯 Integrate Master Orchestrator
- 🎯 End-to-end testing with introspection logging

### Week 5-6 (Nov 25 - Dec 8)
- 🎯 30 days of live paper trading
- 🎯 Tune introspection thresholds
- 🎯 Monitor self-debugging outputs

---

## Benefits of Introspection

### 1. Self-Debugging
- Agents catch errors **before** they happen
- Reduced manual debugging time
- Faster iteration cycles

### 2. Bias Detection
- Agents identify when news sentiment overrides technicals
- Prevents FOMO-driven trades
- More rational decision-making

### 3. Auditability
- Every decision has explicit reasoning trail
- Easy to diagnose why trades succeeded/failed
- Regulatory compliance (if needed in future)

### 4. Safety
- Multiple layers of safety checks
- Agents refuse to execute unsafe trades
- Circuit breakers integrated into agent reasoning

### 5. Continuous Improvement
- Agents log what worked/didn't work
- Introspection data feeds into RL system
- System gets smarter over time

---

## References

- [Anthropic Introspection Research](https://www.anthropic.com/research/introspection)
- [Claude Agents SDK Best Practices](https://skywork.ai/blog/claude-agent-sdk-best-practices-ai-agents-2025/)
- [Building Agents with Claude Code SDK](https://blog.promptlayer.com/building-agents-with-claude-codes-sdk/)
- [Anthropic: Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)
