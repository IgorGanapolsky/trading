# Lesson Learned: AI-Friendly Repository Structure (Dec 11, 2025)

**ID**: ll_015
**Date**: December 11, 2025
**Severity**: MEDIUM
**Category**: AI/ML, Developer Experience, Documentation, Best Practices
**Impact**: Improved AI agent comprehension, reduced context window waste, better multi-agent coordination

## Executive Summary

Research into December 2025 best practices revealed that making repositories AI/LLM-agent friendly
requires specific standards and structures. This lesson documents the implementation of these standards
and the rationale behind them.

## The Problem

Before implementing AI-friendly standards:
- AI agents wasted context on understanding repo structure
- Multiple AI tools (Claude, Cursor, Copilot) needed separate configs
- No machine-readable index for AI systems to quickly understand project
- Module-specific context was not available (flat documentation)

## The Solution

### 1. AGENTS.md Standard (Universal)

**What**: A README specifically for AI agents, backed by OpenAI, Anthropic, Google, and Linux Foundation.
**Adoption**: 20,000+ repositories as of December 2025.

```markdown
# AGENTS.md structure:
- Tech stack with versions
- Build/test commands
- Coding conventions
- Boundaries (never touch X)
- Good/bad code examples
```

### 2. llms.txt Specification

**What**: Machine-readable index file for AI systems (like robots.txt for LLMs).
**Adopted by**: Cloudflare, Anthropic, Perplexity, LangChain.

```markdown
# llms.txt structure:
- Project overview
- Documentation links
- Source code organization
- Key files and their purposes
```

### 3. Hierarchical AGENTS.md

**Pattern**: Nested AGENTS.md files for module-specific context.
**Example**: OpenAI's repository uses 88 nested AGENTS.md files.

```
src/orchestrator/AGENTS.md  # Entry point rules
src/safety/AGENTS.md        # Risk management rules
src/strategies/AGENTS.md    # Trading strategy rules
tests/AGENTS.md             # Testing guidelines
```

## Files Created

| File | Purpose |
|------|---------|
| `AGENTS.md` | Universal AI instructions (enhanced) |
| `llms.txt` | Machine-readable project index |
| `src/orchestrator/AGENTS.md` | Orchestrator module rules |
| `src/safety/AGENTS.md` | Safety module rules |
| `src/strategies/AGENTS.md` | Strategy module rules |
| `src/ml/AGENTS.md` | ML module rules |
| `tests/AGENTS.md` | Test guidelines |
| `docs/ai-friendly-repo-guide.md` | Full research documentation |

## Key Principles

### 1. Structure Over Ambiguity
AI needs explicit boundaries and clear organization. Specify what NOT to touch.

### 2. Types Everywhere
Type annotations are AI's roadmap to understanding code.

### 3. Tests as Specifications
AI reads tests to understand expected behavior. Use BDD-style naming.

### 4. Config Format Preference
TOML > JSON > YAML (TOML supports comments, is copy-paste safe).

### 5. Explain WHY, Not WHAT
Comments should explain rationale, not restate code.

## Research Sources

- AGENTS.md Standard: https://agents.md (20k+ repos)
- llms.txt Specification: https://llmstxt.org (Anthropic, Cloudflare adoption)
- Anthropic: "Claude Code Best Practices"
- GitHub Blog: "How to Write a Great AGENTS.md"

## Integration with Existing Systems

### RAG Integration
- Lessons learned are now indexed with AI-friendly metadata
- Pre-merge check queries RAG before any merge
- Auto-learning tests generated from lessons

### ML Pipeline Integration
- Anomaly detector uses learned patterns from lessons
- Pattern detection improved with structured documentation

## Metrics to Track

| Metric | Target | Current |
|--------|--------|---------|
| AI context waste | < 10% | Baseline needed |
| Tool compatibility | All 4 major tools | Achieved |
| Module coverage | 100% key modules | 5/5 |
| Documentation freshness | < 30 days | Current |

## Recommendations

1. **Update AGENTS.md monthly** with lessons learned
2. **Add nested AGENTS.md** when creating new modules
3. **Use llms.txt** as the entry point for AI exploration
4. **Cross-link** between tool-specific configs

## Tags

#ai #llm #documentation #agents-md #llms-txt #best-practices #multi-agent #context-optimization

## Change Log

- 2025-12-11: Initial research and implementation
- 2025-12-11: Created AGENTS.md, llms.txt, nested module files
- 2025-12-11: Added docs/ai-friendly-repo-guide.md
