# DeepAgents Usage Guide

Complete guide for using deepagents in production trading workflows.

## Quick Start

### Basic Usage

```python
from src.deepagents_integration import create_trading_research_agent

# Create agent
agent = create_trading_research_agent()

# Use for research
result = await agent.ainvoke({
    "messages": [{
        "role": "user",
        "content": "Research NVDA and provide investment recommendation"
    }]
})
```

### Integration with Existing Framework

```python
from src.deepagents_integration.bridge import create_deepagents_research_agent
from src.orchestrator.main import TradingOrchestrator, OrchestratorConfig

# Create deepagents agent
deepagents_research = create_deepagents_research_agent()

# Add to orchestrator
orchestrator = TradingOrchestrator(
    OrchestratorConfig(
        agents=[deepagents_research],
        state_provider=FileStateProvider("data/system_state.json"),
    )
)
```

## Use Cases

### 1. Comprehensive Market Research

**When to use**: Deep analysis requiring multiple data sources and planning.

```python
from src.deepagents_integration import create_trading_research_agent

agent = create_trading_research_agent()

query = """
Research AAPL stock comprehensively:
1. Analyze price action and technical indicators
2. Review sentiment from news and social media
3. Assess market regime
4. Provide investment recommendation with risk assessment
5. Save analysis to file for future reference
"""

result = await agent.ainvoke({"messages": [{"role": "user", "content": query}]})
```

**Benefits**:
- Automatic task breakdown with `write_todos`
- Filesystem integration for saving results
- Context management for long analyses
- Sub-agent delegation for specialized tasks

### 2. Real-Time Market Analysis

**When to use**: Quick analysis with sub-agent risk assessment.

```python
from src.deepagents_integration import create_market_analysis_agent

# Define risk sub-agent
risk_subagent = {
    "name": "risk-analyst",
    "description": "Specialized risk assessment",
    "system_prompt": "You assess portfolio risk and position sizing...",
    "tools": [],
}

agent = create_market_analysis_agent(subagents=[risk_subagent])

query = """
Analyze SPY for trading opportunity:
1. Check current market conditions
2. Delegate risk assessment to risk-analyst
3. Generate trade recommendation
"""

result = await agent.ainvoke({"messages": [{"role": "user", "content": query}]})
```

### 3. Hybrid Approach

**When to use**: Combine deepagents with rule-based logic.

```python
from src.deepagents_integration.bridge import HybridTradingAgent
from src.agents.signal_agent import SignalAgent

# Create hybrid agent
hybrid = HybridTradingAgent(
    agent_name="hybrid-signal",
    deepagent=create_market_analysis_agent(),
    fallback_agent=SignalAgent(),
)

# Use in orchestrator
# Falls back to SignalAgent if deepagent fails
```

## Configuration

### Environment Variables

```bash
# Required
export ANTHROPIC_API_KEY=your_key_here

# Optional
export LANGCHAIN_MODEL=anthropic:claude-sonnet-4-5-20250929
export LANGCHAIN_TEMPERATURE=0.3
```

### Model Selection

```python
from langchain.chat_models import init_chat_model
from src.deepagents_integration import create_trading_research_agent

# Use Claude Sonnet (default)
agent = create_trading_research_agent(
    model="anthropic:claude-sonnet-4-5-20250929",
    temperature=0.3,
)

# Use Claude Opus for complex analysis
agent = create_trading_research_agent(
    model="anthropic:claude-opus-4-20250514",
    temperature=0.2,
)

# Use GPT-4
agent = create_trading_research_agent(
    model="openai:gpt-4o",
    temperature=0.3,
)
```

### Temperature Settings

- **Research**: `0.3` - Balanced creativity and accuracy
- **Analysis**: `0.2` - More deterministic for trading decisions
- **Creative Tasks**: `0.5-0.7` - More exploratory

## Best Practices

### 1. Planning First

Always let agents plan complex tasks:

```python
query = """
Break down this research task using write_todos, then execute:
1. Gather market data
2. Analyze sentiment
3. Calculate technical indicators
4. Generate report
"""
```

### 2. Use Filesystem for Persistence

Agents automatically save large results, but you can guide them:

```python
query = """
Save your analysis to data/analysis/NVDA_2025-01-15.md
Include all supporting data and reasoning.
"""
```

### 3. Delegate Specialized Tasks

Use sub-agents for complex subtasks:

```python
subagents = [
    {
        "name": "risk-analyst",
        "description": "Risk assessment specialist",
        "system_prompt": "You specialize in portfolio risk...",
        "tools": [],
    },
    {
        "name": "technical-analyst",
        "description": "Technical analysis specialist",
        "system_prompt": "You specialize in technical indicators...",
        "tools": [analyze_technical_indicators],
    },
]

agent = create_market_analysis_agent(subagents=subagents)
```

### 4. Monitor Costs

Deepagents includes prompt caching to reduce costs:

- Static system prompts are cached
- Repeated queries benefit from caching
- Monitor API usage in Anthropic dashboard

### 5. Error Handling

Always handle errors gracefully:

```python
from src.deepagents_integration.bridge import HybridTradingAgent

# Hybrid agent automatically falls back
hybrid = HybridTradingAgent(
    agent_name="research",
    deepagent=create_trading_research_agent(),
    fallback_agent=traditional_research_agent,
)
```

## Production Deployment

### 1. Integration with Orchestrator

```python
# src/orchestrator/main.py
from src.deepagents_integration.bridge import create_deepagents_research_agent

def create_orchestrator():
    return TradingOrchestrator(
        OrchestratorConfig(
            agents=[
                DataAgent(),
                create_deepagents_research_agent(),  # Add deepagents
                # ... other agents
            ],
            state_provider=FileStateProvider("data/system_state.json"),
        )
    )
```

### 2. Monitoring

```python
import logging

logger = logging.getLogger(__name__)

# Deepagents logs automatically
# Monitor for:
# - Tool call counts
# - Context length
# - Sub-agent invocations
# - Filesystem operations
```

### 3. Cost Management

- Use prompt caching (automatic)
- Set temperature appropriately
- Limit context length with summarization (automatic)
- Monitor Anthropic dashboard

## Troubleshooting

### Python 3.14 Compatibility

**Issue**: Import errors with langchain-core

**Solution**: Use Python 3.11-3.13

```bash
# Check Python version
python3 --version

# Use pyenv to switch versions
pyenv install 3.13.0
pyenv local 3.13.0
```

### Import Errors

**Issue**: Cannot import deepagents tools

**Solution**: Ensure dependencies installed

```bash
python3 -m pip install -r requirements.txt
python3 -m pip install ".[deepagents]"
```

### Agent Not Planning

**Issue**: Agent doesn't use `write_todos`

**Solution**: Explicitly request planning in prompt:

```python
query = """
Use write_todos to plan this task, then execute:
[your task here]
"""
```

### Context Overflow

**Issue**: Context window exceeded

**Solution**: Deepagents handles this automatically with:
- Filesystem offloading (>20K tokens)
- Automatic summarization (170K tokens)
- Sub-agent delegation

## Examples

See `examples/deepagents_trading_example.py` for complete examples:
- Research agent usage
- Market analysis with sub-agents
- Planning workflow demonstration
- Orchestrator integration

## References

- [DeepAgents Documentation](https://docs.langchain.com/oss/python/deepagents/overview)
- [DeepAgents Quickstarts](https://github.com/langchain-ai/deepagents-quickstarts)
- [LangChain Agents](https://python.langchain.com/docs/modules/agents/)
