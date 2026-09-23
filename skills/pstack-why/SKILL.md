---
name: pstack-why
description: "Conduct deep historical archaeology and architectural rationale investigation using Git blame, PR discussions, and RAG lessons. Use when questioning why an architectural constraint exists, investigating regressions, or evaluating whether a legacy rule can be relaxed."
---

# pstack: /why (Archaeology & Architectural Rationale)

The `/why` skill implements the historical context discipline from the **pstack** engineering playbook. Rather than guessing why a constraint, pattern, or safety check was introduced, `/why` systematically uncovers the historical evidence: commits, PRs, issues, post-mortems, and RAG lessons learned.

---

## Operating Invariants

1. **Evidence Over Speculation**: Every claim about why code exists must cite a specific commit SHA, PR number, issue key, or RAG lesson file.
2. **Identify the Catalyst Incident**: Determine whether a pattern was born from a production outage, an account risk boundary violation, a CI loop regression, or a compliance audit.
3. **Respect Hard Bounds**: Code that appears awkward or redundant often exists to defend against catastrophic edge cases. Never remove safety logic without discovering its origin.

---

## Archaeological Investigation Playbook

### Step 1: Git Blame & Commit Range
Pinpoint the exact commit introducing the target lines:
```bash
# Locate line numbers and commits
git log -S "<symbol_or_string>" -p -- path/to/file.py
git blame -L <start>,<end> path/to/file.py
```
Note the commit SHA and author message.

### Step 2: Query RAG Lessons Learned
Search curated operator memory:
```bash
# Search local RAG markdown lessons
grep -rni "<topic>" rag_knowledge/lessons_learned/
python scripts/rag_query.py --query "<topic>"
```
Key institutional lessons in this repository:
- `LL-671`: Strict Corporate vs. Personal Identity Separation (Zero `@ecisolutions.com` boundary).
- `LL-670`: Session Directives & Operator Memory Preservation.
- Iron Condor Retirement: Lessons explaining why `iron_condor` entries were terminated due to unhedged tail risk during high-volatility regime shifts.
- Paper-First Validation Gate: Why live capital is locked until `n >= 30` closed paired trades prove positive expectancy.

### Step 3: Check PR Discussions & Reviews
Retrieve the PR context from GitHub:
```bash
gh pr view <pr_number> --comments
gh pr view <pr_number> --json title,body,reviews
```

### Step 4: Check Multi-Agent Obsidian Vault Handoffs
Review historical handoff notes in `~/Documents/Igor/Agents/Handoffs/` or claim notes in `~/Documents/AI-Agent-Sync/Handoffs/linear-claims/`.

### Step 5: Synthesize Context Report
Produce an artifact with:
- **Root Problem**: What triggered the code addition?
- **Alternatives Considered**: What was attempted and why did it fail?
- **Active Constraints**: Is the reason for this constraint still active today?
- **Decision Recommendation**: Keep, tighten, or safely refactor.
