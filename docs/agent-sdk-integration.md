# Claude Agent SDK Integration

**Date**: December 2025
**Status**: Implemented

## Overview

This document describes the integration of new Claude Agent SDK features announced in December 2025:

1. **1M Context Windows** - 5x larger context for full codebase awareness
2. **Sandboxing** - Secure code execution for trading agents
3. **SDK V2** - Modern agent interfaces

## Features

### 1. One Million Token Context Windows

The system now supports 1M token context windows (up from 200K), enabling:

- Load entire trading codebase + history in a single context
- Full market data awareness across multiple timeframes
- Comprehensive risk analysis with complete portfolio context
- Multi-agent coordination with shared full context

**Configuration** (`src/agent_framework/agent_sdk_config.py`):

```python
from src.agent_framework import get_agent_sdk_config, ContextWindowSize

config = get_agent_sdk_config()
# Context size: 1,000,000 tokens (1M)
print(f"Context size: {config.context_size.value:,}")
```

**Agent-Specific Allocations**:

| Agent | Context Allocation |
|-------|-------------------|
| Meta Agent | 400,000 tokens |
| Research Agent | 200,000 tokens |
| Signal Agent | 150,000 tokens |
| RL Agent | 150,000 tokens |
| Risk Agent | 100,000 tokens |
| Execution Agent | 50,000 tokens |

### 2. Sandboxing Configuration

Secure code execution with configurable isolation:

**Sandbox Modes**:
- `native` - Lightweight OS-level isolation (default)
- `docker` - Container isolation for production
- `gvisor` - Maximum security with syscall interception

**Configuration** (`config/sandbox_config.json`):

```json
{
  "sandbox": {
    "enabled": true,
    "mode": "native",
    "network": {
      "allowedDomains": ["api.alpaca.markets", "api.anthropic.com"]
    },
    "filesystem": {
      "allowedPaths": ["./data", "./reports"],
      "readOnlyPaths": ["./src", "./config"]
    }
  }
}
```

**Agent-Specific Sandbox Settings**:
- Research agents: Full network access for data fetching
- Execution agents: Limited to trading API domains only
- RL agents: No network, filesystem access to model storage

### 3. SDK V2 Integration

The codebase is prepared for Claude Agent SDK V2:

**Beta Features Enabled**:
```python
beta_features = [
    "context-1m-2025-08-07",  # 1M context
]
```

**API Integration**:
```python
config = get_agent_sdk_config()
api_params = config.get_api_params()
# Returns: {"model": "...", "max_tokens": ..., "betas": [...]}
```

## Usage

### Basic Usage

```python
from src.agent_framework import get_agent_sdk_config, get_context_engine

# Get SDK configuration
sdk_config = get_agent_sdk_config()

# Get context engine with 1M support
context_engine = get_context_engine()

# Get agent context (automatically uses 1M limits)
context = context_engine.get_agent_context(
    agent_id="research_agent",
    use_1m_context=True
)
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CLAUDE_CONTEXT_1M` | `true` | Enable 1M context windows |
| `CLAUDE_MODEL` | `claude-sonnet-4-5-20250929` | Default model |
| `CLAUDE_SANDBOX_DISABLED` | `false` | Disable sandboxing |
| `CLAUDE_SANDBOX_MODE` | `native` | Sandbox mode |

### Programmatic Configuration

```python
from src.agent_framework import (
    AgentSDKConfig,
    ContextWindowSize,
    SandboxMode,
    configure_agent_sdk
)

# Custom configuration
config = AgentSDKConfig(
    context_size=ContextWindowSize.EXTENDED_1M,
    default_model="claude-opus-4-5-20251101",
    sandbox=SandboxSettings(
        enabled=True,
        mode=SandboxMode.DOCKER
    )
)

configure_agent_sdk(config)
```

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                 Agent SDK Config                     │
│  - Context window settings (1M support)             │
│  - Beta feature flags                               │
│  - Model selection                                  │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────┐
│               Context Engine                         │
│  - Dynamic context allocation per agent             │
│  - Multi-timescale memory (nested learning)         │
│  - Semantic blueprints                              │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────┐
│              Sandbox Runtime                         │
│  - Network isolation                                │
│  - Filesystem restrictions                          │
│  - Command allowlists                               │
└─────────────────────────────────────────────────────┘
```

## Benefits for Trading

1. **Full Market Context**: Load entire trading history + current positions + market data
2. **Comprehensive Analysis**: RL agents can see full learning history in context
3. **Better Coordination**: Meta agent has complete view for orchestration
4. **Secure Execution**: Sandboxed trading prevents unauthorized actions
5. **Faster Iteration**: More context = fewer round trips = faster decisions

## Requirements

- Anthropic API Tier 4 or custom rate limits (for 1M context)
- `anthropic>=0.73.0` Python SDK
- Docker (optional, for Docker sandbox mode)

## References

- [Claude Agent SDK Overview](https://platform.claude.com/docs/en/agent-sdk/overview)
- [1M Context Windows](https://docs.claude.com/en/docs/build-with-claude/context-windows)
- [Sandboxing Documentation](https://code.claude.com/docs/en/sandboxing)
- [Anthropic Engineering Blog](https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk)
