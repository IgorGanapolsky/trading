# AI-Friendly Repository Guide (December 2025)

> Research-backed best practices for making repositories AI/LLM agent-friendly.

## Executive Summary

This guide documents the December 2025 best practices for making codebases work well with AI coding assistants (Claude Code, Cursor, GitHub Copilot, Aider, etc.).

**Key Finding**: The **AGENTS.md** standard has emerged as the universal instruction file for AI agents, co-founded by OpenAI, Anthropic, and Google, now managed by the Linux Foundation. Over **20,000+ repositories** have adopted it.

## Standards Implemented in This Repo

| Standard | File | Purpose |
|----------|------|---------|
| AGENTS.md | `/AGENTS.md` | Universal AI instructions |
| llms.txt | `/llms.txt` | Machine-readable index |
| Nested AGENTS.md | `src/*/AGENTS.md` | Module-specific rules |
| CLAUDE.md | `.claude/CLAUDE.md` | Claude-specific extensions |
| .cursorrules | `/.cursorrules` | Cursor IDE rules |

## 1. AGENTS.md Standard

### What Is It?

AGENTS.md is a README specifically for AI agents. It tells AI tools:
- What tech stack you use (with versions)
- How to build/test the project
- Coding conventions to follow
- What files to never touch
- Examples of good and bad patterns

### Why It Matters

- **Cross-tool compatible**: Works with Claude Code, Cursor, Copilot, Aider
- **Hierarchical**: Root + nested files for context-specific rules
- **Industry standard**: Backed by OpenAI, Anthropic, Google

### Best Practices

1. **Keep under 500 lines** per file
2. **Include concrete examples** (not just abstract rules)
3. **Specify tech stack with versions**
4. **Document boundaries** (what NOT to touch)
5. **Use nested files** for large codebases

## 2. llms.txt Specification

### What Is It?

A machine-readable index file (like robots.txt for AI) that tells LLMs:
- What documentation exists
- Where to find specific information
- Project structure overview

### Format

```markdown
# Project Name

> One-sentence description

## Core Documentation
- [Link](path): Description

## Source Code
- [Link](path): Description
```

### Who Uses It?

- Cloudflare
- Anthropic
- Perplexity
- LangChain

## 3. Type Annotations (Critical)

### Why Types Matter for AI

AI coding assistants use type hints as a **roadmap** to understand code:
- Generate more accurate suggestions
- Catch errors before runtime
- Understand function contracts

### Python

```python
from typing import Optional
from decimal import Decimal

def calculate_risk(
    equity: Decimal,
    position_size: Decimal,
    stop_loss: Decimal
) -> Optional[Decimal]:
    """Calculate risk for a position."""
    pass
```

### TypeScript

```typescript
interface TradeSignal {
  ticker: string;
  action: 'buy' | 'sell';
  quantity: number;
  confidence: number;
}

function validateSignal(signal: TradeSignal): boolean {
  // ...
}
```

## 4. Documentation for AI

### Structured Comments

AI understands code structure better when comments explain **WHY**, not **WHAT**:

```python
# Good - explains rationale
# Use exponential backoff because Alpaca rate limits are tiered:
# 200/min normally, 2/min after violation
retry_delay = 2 ** attempt_number

# Bad - restates code
# Multiply 2 by itself attempt_number times
retry_delay = 2 ** attempt_number
```

### Docstrings with Examples

```python
def calculate_position_size(equity: float, risk: float) -> int:
    """Calculate position size based on risk.

    Args:
        equity: Account equity in USD
        risk: Maximum risk as decimal (0.02 = 2%)

    Returns:
        Number of shares to purchase

    Example:
        >>> calculate_position_size(10000, 0.02)
        66  # Risk $200 on a $3 stop
    """
```

## 5. Test Organization

### Tests as Specifications

In 2025, tests serve as **specifications** for AI:
1. AI reads tests to understand expected behavior
2. AI generates code to pass your tests
3. Tests validate AI-generated code

### BDD-Style Naming

```python
def test_circuit_breaker_halts_trading_after_3_percent_daily_loss():
    """
    GIVEN a portfolio down 3% today
    WHEN circuit breaker evaluates
    THEN trading should be halted
    """
    pass
```

### Structure

```
tests/
├── unit/           # Fast, isolated tests
├── safety/         # Safety-critical (MANDATORY)
├── integration/    # Multi-component
└── fixtures/       # Test data
```

## 6. Configuration Formats

### Preference Order

1. **TOML** - Best for config (supports comments, type-safe)
2. **JSON** - Best for data interchange
3. **YAML** - Only where required (CI/CD)

### Why TOML?

```toml
# Comments supported
[trading]
daily_budget = 10.50  # USD per day
max_positions = 5

[risk]
max_per_trade = 0.02  # 2% max risk
```

vs JSON (no comments allowed):
```json
{
  "trading": {
    "daily_budget": 10.50,
    "max_positions": 5
  }
}
```

## 7. Multi-Agent Coordination

### Git Worktrees

For multiple AI agents working simultaneously:

```bash
# Create isolated worktree
git worktree add ../trading-feature -b claude/feature-name

# Work in isolation
cd ../trading-feature

# Clean up
git worktree remove ../trading-feature
```

### Module Ownership

Define in nested AGENTS.md files which agent "owns" which module:

```markdown
## Module Ownership
- `src/orchestrator/` - Primary agent
- `src/strategies/` - Strategy agent
- `src/ml/` - ML research agent
```

## 8. Context Window Optimization

### The Problem

AI context windows are limited. Long files exhaust them.

### Solutions

1. **Artifact pattern**: Store references, not full content
2. **Context summarization**: Summarize old data, keep recent verbatim
3. **Stay under 70%** context usage
4. **Use RAG** for large knowledge bases

## 9. Tool-Specific Configuration

### Claude Code

- Primary: `.claude/CLAUDE.md`
- Commands: `.claude/commands/*.md`
- Skills: `.claude/skills/*/SKILL.md`

### Cursor IDE

- Modern: `.cursor/rules/*.mdc`
- Legacy: `.cursorrules`
- Keep rules under 500 lines

### GitHub Copilot

- Primary: `.github/copilot-instructions.md`
- Prompts: `.github/prompts/*.prompt.md`
- Supports AGENTS.md natively

### Aider

- Config: `.aider.conf.yml`
- Conventions: `CONVENTIONS.md`

## 10. Implementation Checklist

### Immediate (Do Today)

- [x] Create `/AGENTS.md` at root
- [x] Create `/llms.txt` index
- [x] Add nested `AGENTS.md` for key modules
- [ ] Enable strict type checking (mypy/TypeScript)
- [ ] Add OpenAPI schema for APIs

### Short-Term (This Week)

- [ ] Audit docstrings for completeness
- [ ] Convert config to TOML where possible
- [ ] Add BDD-style test names
- [ ] Document common anti-patterns

### Long-Term (This Month)

- [ ] Build code embedding index (semantic search)
- [ ] Implement context summarization
- [ ] Set up multi-agent orchestration
- [ ] Create architecture decision records

## Sources

### AGENTS.md Standard
- [agents.md Official Site](https://agents.md)
- [AGENTS.md Emerges as Open Standard - InfoQ](https://www.infoq.com/news/2025/08/agents-md/)
- [GitHub Blog: How to Write a Great AGENTS.md](https://github.blog/ai-and-ml/github-copilot/how-to-write-a-great-agents-md/)

### llms.txt Specification
- [llms.txt Official Site](https://llmstxt.org/)
- Adopted by: Cloudflare, Anthropic, Perplexity, LangChain

### Claude Code Best Practices
- [Claude Code: Best practices for agentic coding - Anthropic](https://www.anthropic.com/engineering/claude-code-best-practices)
- [How I use Claude Code - Builder.io](https://www.builder.io/blog/claude-code)

### Multi-Agent Systems
- [Anthropic: Multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)
- [Git Worktrees for AI - Nx Blog](https://nx.dev/blog/git-worktrees-ai-agents)

### Context Engineering
- [Anthropic: Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [JetBrains: Efficient Context Management](https://blog.jetbrains.com/research/2025/12/efficient-context-management/)

---

*Last Updated: December 2025*
*Research conducted using parallel agent architecture*
