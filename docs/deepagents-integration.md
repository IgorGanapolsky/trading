# DeepAgents Integration

## Overview

DeepAgents has been integrated into the main trading loop as of November 25, 2025. This integration enables planning-based trading analysis with sub-agent delegation capabilities.

## Architecture

### Integration Flow

The trading execution flow now follows this priority order:

1. **DeepAgents** (Planning-based agent) - `_execute_core_strategy_with_deepagents()`
2. **ADK Orchestrator** (Go-based multi-agent) - `_execute_core_strategy_with_adk()`
3. **Core Strategy** (Python-based legacy) - `_execute_core_strategy()`

Each integration attempts to make a trading decision. If it succeeds, the flow stops. If it fails or returns False, the next integration is tried.

### Current Implementation Status

**Phase 1: Analysis Only (Current)**
- DeepAgents is **disabled** by default (install + set env to enable)
- Runs comprehensive market analysis
- Logs recommendations and insights
- **Does NOT execute trades** (returns False to fall back to Core Strategy)
- Serves as validation layer to verify DeepAgents output quality

**Phase 2: Trade Execution (Future)**
- Parse DeepAgents JSON recommendations
- Validate position sizing and risk parameters
- Execute trades via AlpacaTrader
- Full autonomous decision-making

## Configuration

### Environment Variables

Add to your `.env` file (defaults to disabled so CI stays lean):

```bash
# DeepAgents - Planning-based trading agent with sub-agent delegation
DEEPAGENTS_ENABLED=false
```

**Values:**
- `true`, `1`, `on`, `yes` → DeepAgents ENABLED
- `false`, `0`, `off`, `no` → DeepAgents DISABLED

**Default:** `false` (enable explicitly once dependencies are installed)

### Dependencies

DeepAgents is now an **optional extra**. Install it only if you plan to run the planning agent:

```bash
# Install base dependencies
python3 -m pip install -r requirements.txt
# Then install the DeepAgents extra
python3 -m pip install ".[deepagents]"
```

If DeepAgents is not installed, the system will:
1. Log a warning during initialization
2. Set `deepagents_adapter = None`
3. Fall back to ADK or Core Strategy

## Code Structure

### Key Files

- **`src/main.py`**
  - `TradingOrchestrator.__init__()` - Initializes DeepAgents adapter
  - `_execute_core_strategy_with_deepagents()` - Executes DeepAgents analysis
  - `_execute_core_strategy()` - Coordinates all integrations

- **`src/deepagents_integration/adapter.py`**
  - `DeepAgentsAdapter` - Wraps deepagent as a TradingAgent
  - `create_analysis_agent_adapter()` - Factory for market analysis agent
  - `create_research_agent_adapter()` - Factory for research agent

- **`src/deepagents_integration/agents.py`**
  - `create_trading_research_agent()` - Research agent with planning tools
  - `create_market_analysis_agent()` - Analysis agent with sub-agents

### Initialization Code

```python
# In TradingOrchestrator._initialize_components()
deepagents_enabled_env = os.getenv("DEEPAGENTS_ENABLED", "false").lower()
deepagents_enabled = deepagents_enabled_env not in {"0", "false", "off", "no"}

if deepagents_enabled:
    try:
        self.deepagents_adapter = create_analysis_agent_adapter(
            agent_name="deepagents-market-analysis"
        )
        self.logger.info("DeepAgents market analysis adapter initialized")
    except Exception as e:
        self.logger.warning(
            f"Failed to initialize DeepAgents (will fall back to core strategy): {e}"
        )
        self.deepagents_adapter = None
```

### Execution Code

```python
# In TradingOrchestrator._execute_core_strategy()
# Try DeepAgents first (planning-based agent with sub-agent delegation)
if self._execute_core_strategy_with_deepagents(account_info):
    self.logger.info("Core Strategy satisfied via DeepAgents")
    return

# Try ADK orchestrator next
if self._execute_core_strategy_with_adk(account_info):
    self.logger.info("Core Strategy satisfied via ADK orchestrator")
    return

# Fall back to legacy Core Strategy
order = self.core_strategy.execute_daily()
```

## How DeepAgents Works

### Query Sent to DeepAgents

```
Analyze the following ETFs for today's trading opportunity: SPY, QQQ, IWM, DIA

Account Context:
- Portfolio Value: $X.XX
- Available Cash: $X.XX
- Buying Power: $X.XX
- Daily Allocation: $X.XX

Risk Limits:
- Max Daily Loss: X%
- Max Position Size: X%
- Max Drawdown: X%
- Stop Loss: X%

Instructions:
1. Fetch market data and technical indicators for each ETF
2. Analyze sentiment if available
3. Identify the best trading opportunity (or recommend HOLD if none)
4. Provide a structured trade recommendation with:
   - Symbol and action (BUY/SELL/HOLD)
   - Position size recommendation
   - Entry price target
   - Stop loss and take profit levels
   - Conviction score (0-1)
   - Risk assessment
   - Supporting reasoning

Output your recommendation in JSON format for easy parsing.
```

### DeepAgents Capabilities

1. **Planning** - Uses `write_todos` to break down analysis tasks
2. **Market Data** - Fetches OHLCV data and technical indicators
3. **Sentiment Analysis** - Queries historical sentiment data
4. **Sub-Agent Delegation** - Can spawn specialized agents for deep dives
5. **Filesystem Tools** - Stores intermediate analysis results
6. **MCP Integration** - Access to Alpaca APIs via MCP tools

### Response Format

DeepAgents returns an `AgentResult` with:

```python
{
    "name": "deepagents-market-analysis",
    "succeeded": True/False,
    "payload": {
        "query": "...",
        "response": {
            # DeepAgents analysis output
            "messages": [...]
        }
    },
    "error": "..." if failed
}
```

## Verification & Testing

### Test Script

Run the integration test:

```bash
python3 test_deepagents_integration.py
```

**Expected Output (with dependencies):**
```
✅ PASS: Import DeepAgents adapter
✅ PASS: Environment variable
✅ PASS: Adapter initialization
✅ PASS: Import TradingOrchestrator
✅ PASS: Initialize TradingOrchestrator
```

### Manual Verification

1. **Check Logs During Initialization:**
   ```
   DeepAgents market analysis adapter initialized
   ```

2. **Check Logs During Execution:**
   ```
   Executing DeepAgents market analysis for core strategy
   DeepAgents analysis complete: {...}
   DeepAgents provided analysis (execution not yet implemented - falling back to core strategy)
   ```

3. **Check Health Status:**
   ```python
   orchestrator.health_status["last_deepagents_analysis"]  # Timestamp
   orchestrator.health_status["deepagents_response"]       # First 500 chars of response
   ```

### Disable DeepAgents

If you need to disable DeepAgents temporarily:

```bash
# Set in .env
DEEPAGENTS_ENABLED=false

# Or via environment variable
export DEEPAGENTS_ENABLED=false
python src/main.py --mode paper --run-once
```

## Monitoring

### Log Messages

**Success:**
```
[INFO] Executing DeepAgents market analysis for core strategy
[INFO] DeepAgents analysis complete: {...}
[INFO] DeepAgents provided analysis (execution not yet implemented - falling back to core strategy)
```

**Failure:**
```
[ERROR] DeepAgents analysis failed: <error message>
[ERROR] DeepAgents evaluation failed: <exception>
```

**Disabled:**
```
[INFO] DeepAgents integration disabled via DEEPAGENTS_ENABLED=false
```

### Health Status Fields

- `last_deepagents_analysis` - ISO timestamp of last DeepAgents execution
- `deepagents_response` - First 500 characters of last response (for debugging)

## Roadmap

### Phase 1: Analysis Only (Current - Nov 25, 2025)
- [x] Integrate DeepAgents into main trading loop
- [x] Document opt-in install/env toggle (`pip install ".[deepagents]"` + `DEEPAGENTS_ENABLED=true`)
- [x] Log analysis and recommendations
- [x] Fall back to Core Strategy for execution
- [x] Validate output quality

### Phase 2: Trade Execution (Future)
- [ ] Parse JSON recommendations from DeepAgents
- [ ] Validate position sizing against risk limits
- [ ] Execute trades via AlpacaTrader
- [ ] Add comprehensive error handling
- [ ] Return True to prevent fallback

### Phase 3: Advanced Features (Future)
- [ ] Multi-symbol analysis with batch processing
- [ ] Sub-agent specialization (risk agent, sentiment agent, etc.)
- [ ] Historical performance tracking
- [ ] A/B testing vs Core Strategy
- [ ] Cost optimization (token usage monitoring)

## Troubleshooting

### DeepAgents Not Running

**Symptom:** No DeepAgents logs in output

**Diagnosis:**
1. Check environment variable: `echo $DEEPAGENTS_ENABLED`
2. Check initialization logs for warnings
3. Verify dependencies: `pip show deepagents langchain langchain-core`

**Solutions:**
- Install optional dependencies: `python3 -m pip install ".[deepagents]"`
- Enable via `.env`: `DEEPAGENTS_ENABLED=true`
- Check for initialization exceptions in logs

### DeepAgents Failing Silently

**Symptom:** DeepAgents runs but always falls back to Core Strategy

**Diagnosis:**
1. Check execution logs for error messages
2. Examine `health_status["deepagents_response"]` for clues
3. Review exception tracebacks in logs

**Solutions:**
- Current behavior is **expected** (Phase 1)
- DeepAgents returns False intentionally to validate output
- Check logs for actual errors vs intentional fallback

### High Latency

**Symptom:** DeepAgents analysis takes too long

**Diagnosis:**
1. Check query complexity (number of symbols, data requests)
2. Monitor LLM API response times
3. Review sub-agent delegation patterns

**Solutions:**
- Reduce symbols in ETF universe for testing
- Adjust temperature and token limits
- Optimize query to reduce tool calls

## Related Documentation

- **Agent Framework:** `docs/agent-framework.md` (if exists)
- **ADK Integration:** `docs/adk-integration.md` (if exists)
- **Trading Strategies:** `README.md` and `src/strategies/`

## Support & Feedback

This integration was implemented per CEO directive on November 24, 2025:
> "Enable ALL dormant systems NOW! We have $100/mo budget. Move towards North Star immediately!"

DeepAgents is enabled by default to maximize decision quality through planning-based analysis and sub-agent delegation.

---

**Last Updated:** November 25, 2025
**Status:** Phase 1 (Analysis Only)
**Next Milestone:** Phase 2 (Trade Execution)
