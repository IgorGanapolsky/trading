---
layout: post
title: "Lesson Learned: CLAUDE.md Bloat Anti-Pattern"
---

# Lesson Learned: CLAUDE.md Bloat Anti-Pattern

**ID**: LL-017
**Impact**: Identified through automated analysis

**Date**: December 12, 2025
**Category**: Agent Optimization
**Severity**: High (wastes 3-4k tokens every conversation)

## The Problem

Our CLAUDE.md grew to ~700 lines / ~14k characters - approximately **7x larger than best practices recommend**.

### What We Had Wrong

| Anti-Pattern | Example | Impact |
|--------------|---------|--------|
| **Token bloat** | 700 lines vs recommended 100-300 | Wastes ~3-4k tokens before work begins |
| **Procedures in CLAUDE.md** | GitHub API curl examples inline | Should be in `.claude/commands/` |
| **Mixed concerns** | Memory + Rules + Procedures together | Violates separation of concerns |
| **Code snippets** | Full curl commands for PR creation | Becomes stale, duplicates scripts |
| **Historical rationale** | "CEO Directive Dec 9, 2025..." | Belongs in `docs/decisions/` |
| **Verbose chain of command** | Multiple paragraphs on CEO/CTO roles | Should be 1-2 lines max |

## Best Practices (Per Anthropic Dec 2025)

### Recommended Structure

```
CLAUDE.md (250 lines MAX)
├── Facts: architecture, tech stack, conventions
├── 1-line pointers to detailed docs
└── Critical rules (1 line each)

.claude/rules/MANDATORY_RULES.md
├── Detailed rule explanations
├── Context and rationale
└── Single source of truth

.claude/commands/
├── create-pr.md (procedure)
├── verify-trade.md (procedure)
└── daily-report.md (procedure)

docs/
├── chain-of-command.md
├── verification-protocols.md
└── decisions/ (historical rationale)
```

### Key Metrics

| Metric | Bad | Good |
|--------|-----|------|
| CLAUDE.md lines | >300 | 100-250 |
| Token consumption | >3000 | <1500 |
| Procedures inline | Any | Zero |
| Code snippets | Any | Zero (use file pointers) |

## Why This Matters

1. **Token waste**: Every conversation starts by loading CLAUDE.md. Bloated = less context for actual work.

2. **Instruction decay**: LLMs read full conversation each turn. Instructions at the beginning lose effectiveness as conversation grows. Shorter = more durable.

3. **Maintenance hell**: Procedures in CLAUDE.md get stale. Slash commands are executable and testable.

4. **No single source of truth**: Same rule in CLAUDE.md + hook + script = divergence over time.

## The Fix

### Before (Anti-Pattern)
```markdown
## GitHub PR Creation Protocol

**YOU HAVE FULL AGENTIC CONTROL TO CREATE AND MERGE PRs!**

**Create PR (via GitHub API - PREFERRED):**
\`\`\`bash
curl -X POST \
  -H "Authorization: token <PAT>" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/IgorGanapolsky/trading/pulls \
  -d '{"title": "feat: description"...}'
\`\`\`
[30 more lines of procedures...]
```

### After (Best Practice)
```markdown
## Git & PRs
- **Rule**: Never merge directly to main (CI bypass caused 0 trades Dec 11)
- **Procedure**: See `.claude/commands/create-pr.md`
- **Automation**: Pre-merge gate in `.claude/hooks/`
```

## Action Items Completed

1. Created `.claude/rules/MANDATORY_RULES.md` - single source of truth for critical rules
2. Moved procedures to `.claude/commands/` as slash commands
3. Reduced CLAUDE.md from ~700 to ~250 lines
4. Removed all inline code snippets (replaced with file pointers)
5. Separated: Memory (CLAUDE.md) / Rules (.claude/rules/) / Procedures (.claude/commands/)

## References

- [Anthropic: Claude Code Best Practices](https://www.anthropic.com/engineering/claude-code-best-practices)
- [HumanLayer: Writing a Good CLAUDE.md](https://www.humanlayer.dev/blog/writing-a-good-claude-md)
- [Claude.com: Using CLAUDE.MD Files](https://claude.com/blog/using-claude-md-files)

## Key Takeaway

> "CLAUDE.md should contain **facts** (what exists, architecture). Slash commands should contain **procedures** (how to do things). Rules files should contain **constraints** (what not to do)."

**Token budget rule of thumb**: CLAUDE.md should use <2% of your context window (~4k tokens max for 200k window).


## Prevention Rules

1. Apply lessons learned from this incident
2. Add automated checks to prevent recurrence
3. Update RAG knowledge base
