# A Practical July 2026 Playbook: Multi-Agent Coding Fleets with a Shared Obsidian Vault

## Executive Summary

A solo founder running 2-5 concurrent coding agents in July 2026 should treat the shared Obsidian vault as a **typed, human-readable bus of record**, never as live mutable state. The coordination substrate is **git worktrees** (one per agent), the synchronization primitive is a **commit + PR + merge ceremony** at every session boundary, and the live runtime signaling between agents uses **MCP** (tool access) and **A2A** (agent-to-agent handoff). The Obsidian vault is updated by humans and by the merge bot, not by parallel writes from agents, which is the single most common cause of corruption in production fleets. Lock TTLs of 30-60 minutes, claim scopes that name directories not files, and a strict "no secrets, no `.env`, no live state in the vault" rule cover the other 80% of failure modes.

This playbook distills patterns now standard in Cursor 2.4, Claude Squad, Composio's Agent Orchestrator, and the Linux Foundation's A2A stack, applied to the specific topology described: a single vault with `Handoffs/`, `Agent-Jobs/running/`, `Agent-State/`, and `Project-Reports/`, with worktrees and a dual-layer lock (in-repo `plan.md` + git worktree branch).

---

## 1. Architecture Recommendation

### 1.1 The five layers

| Layer | What lives here | Mutability | Owner |
|---|---|---|---|
| **L1 - Codebase (git)** | Source, tests, configs | Edit by one agent per worktree | The agent that owns the worktree |
| **L2 - Coordination (git)** | `plan.md`, `agent-jobs/<id>/plan.md`, branch names, PRs | Edit-then-commit | Lead human or orchestrator |
| **L3 - Bus of record (Obsidian, git-backed)** | `Handoffs/`, `Agent-Jobs/running/`, `Agent-State/`, `Project-Reports/` | Append-only via PR merge | Merge bot / human |
| **L4 - Live runtime (process / IPC)** | MCP servers, A2A agents, leases, in-memory claims | Ephemeral, TTL-bounded | Orchestrator |
| **L5 - Telemetry** | Logs, traces, spend, tool-call stats | Append-only | Observability stack |

The cardinal rule: **only one layer is writable at a time per resource.** Code lives in L1; the vault in L3 is updated *after* the merge, never concurrently. Addy Osmani's "Code Agent Orchestra" frame (March 26, 2026) puts this as Levels 5-8 of agentic coding; once you orchestrate, you must enforce non-overlapping scopes and a synchronous hand-off gate [1].

### 1.2 Worktree-per-agent as the default

Every long-running agent gets its own worktree at `git worktree add ../wt-<agent>-<task> -b agent/<agent>/<task>`. This is now the default in Claude Squad, Composio's Agent Orchestrator, Cursor 2.0+, and CodeAgentSwarm, and it is the only pattern that scales past two concurrent agents [2][3][4]. Each worktree has its own:

- Branch and dirty state, so two agents can edit the same file without trampling.
- Working `.git/index`, so concurrent `git add` does not produce `index.lock` contention (a top failure mode documented in the Termdock setup guide) [2].
- Lock file `.claude/claim-<task>.lock` *inside the worktree*, never in shared storage.

When the work is done, the agent opens a PR back to `main`. The PR is the only commit the vault observes; the vault update is the *next* PR.

### 1.3 Obsidian-as-bus, not Obsidian-as-state

A personal Obsidian vault is an excellent **human-readable bus of record** for multi-agent fleets in 2026: it is git-versioned, Markdown-native, and supported by typed query plugins (Bases 1.9+, the new CLI in 1.12) and an MCP server such as `obsidian-mind`'s `qmd` tool that exposes `mcp__qmd__query`, `mcp__qmd__get`, and `mcp__qmd__multi_get` so agents read the vault through the same typed contract they use for everything else [5][6]. It is **not** good as live mutable state; parallel writes from agents are a documented failure mode that produces merge churn, dataview staleness, and Bases index corruption.

Three hygiene rules cover most incidents:

1. **Append-only semantics.** Notes in `Handoffs/` and `Project-Reports/` are written once and never edited in place; corrections are new dated notes that link back.
2. **One writer at a time per folder.** The `Agent-Jobs/running/` directory is owned by the orchestrator; agents may only `touch` lease files inside their own `Agent-Jobs/<agent>/<task>/` subdirectory.
3. **Vault is rebuilt from PRs.** If the vault drifts, regenerate it from PR descriptions and commit history; never hand-edit to "fix" drift while agents are running.

### 1.4 Coordination primitives

- **Advisory leases** for shared resources (`docs/`, migrations, lockfiles) with TTL of 30-60 min; renew on tool-call boundary, release on PR open.
- **Claims** on directories, not files (e.g. `src/payments/**`), to reduce false conflicts.
- **Planner-Worker-Judge topology** for any task > 1 hour of agent time: one planner writes the plan, N workers execute in isolated worktrees, one judge reviews the diff. This is Cursor 2.4's default agent architecture and the only pattern with published production numbers in mid-2026 [3][4].
- **A2A for cross-agent handoffs**, MCP for tool/data access. The Linux Foundation A2A Protocol moved to GA in April 2026 with 150+ adopter organizations; use it when one agent must *delegate a task* to another, not for sharing memory [7].
- **MCP shared state only through typed tools.** The MCP registry in 2026 ships with Postgres, Redis, and CRDT servers; treat them as the canonical bus for live state when you actually need it.

### 1.5 Session-boundary ledger vs real-time locks

Use a **session-boundary ledger**, not real-time locks, for coordination between agents. Real-time locks add latency, race conditions, and lock-leak bugs; the session-boundary ledger (PR + merge + vault update) is async, human-readable, and reversible. Real-time locks are appropriate only for the *shared mutable state* inside a worktree (the `index.lock` problem) and for live runtime resources (a Postgres row being updated, a port being held). For everything else, the PR gate is the lock.

---

## 2. Anti-Patterns to Avoid

These are the failure modes that recur in post-mortems from Cursor, Claude Squad, Composio Agent Orchestrator, and independent fleets through 2025-2026.

1. **Sharing one worktree across agents.** Two agents in `/repo` will silently overwrite each other's `index.lock`, `HEAD`, and untracked files. Always one worktree per agent, always a fresh branch [2][4].
2. **Long-lived leases with no TTL.** Leases without TTL become deadlocks when an agent crashes. Use 30-60 min TTL, renew on heart-beat, expire on PR open [2].
3. **Vault as live mutable state.** Agents writing to `Agent-State/` concurrently produce merge churn and dataview staleness. Vault writes happen *after* merge, never during [5].
4. **Secrets in the vault.** Markdown, wikilinks, and Bases views leak fast. Keep `~/.config/<agent>/` credentials, not `~/Documents/AI-Agent-Sync/`. Scan with `gitleaks` pre-commit [1].
5. **Free-form branch names.** `fix-stuff`, `agent-1`, `tmp` lead to collisions and lost PRs. Use `agent/<handle>/<task-slug>` and enforce in CI [2][3].
6. **Monolithic orchestrator with no judge.** A planner that also executes produces unreviewed code. The Planner-Worker-Judge split is now the default in Cursor 2.4 and Composio for any task with > 1 hour of agent time [3][4].
7. **Too many MCP servers / skills.** AgentPatterns' 2026 corpus shows that stacking planning + memory + retrieval + reflection often *degrades* agent quality; context-budget contention and vocabulary collisions cancel individual gains [8]. Three MCP servers is a working ceiling; add a fourth only after measuring.
8. **Letting agents push to `main` directly.** Mandate PR + human review or auto-merge only after CI + a separate judge agent. Cursor, Claude Squad, and Composio all enforce PR-only in their default configs [3][4].
9. **Polling the vault from agents.** Reads go through MCP tools with caching; polling wastes context and produces stale snapshots. The obsidian-mind MCP server exposes typed `query`/`get`/`multi_get` so agents only see the latest snapshot on demand [5].
10. **Treating Linear/GitHub Issues as a substitute for the vault.** Issue trackers do not carry epistemic state ("we tried X and it failed because Y"). Keep the vault for *context*, the tracker for *tasks* [9].

---

## 3. July-2026 Checklist for a Solo Founder Fleet

Use this as the launch runbook for a 2-5 agent fleet. Tick every box before the first parallel run.

### Setup (one-time)
- [ ] Initialize vault: `git init ~/Documents/AI-Agent-Sync` and add to remote (private).
- [ ] Create folder layout: `Handoffs/`, `Agent-Jobs/{running,queued,done}/`, `Agent-State/`, `Project-Reports/`, `_system/`.
- [ ] Enable Obsidian Bases (1.9+) and install `obsidian-mind` MCP server with `qmd` tools [5][6].
- [ ] Add `.gitignore` patterns: `.obsidian/workspace.json`, `.obsidian/cache`, `.trash/`, `*.swp`, `_system/.locks/`.
- [ ] Install `gitleaks` pre-commit hook; block API keys, JWTs, PEM blocks.
- [ ] Pin each agent to a deterministic handle (e.g. `claude`, `codex`, `cursor`, `hermes`, `grok`, `antigravity`) — used in branch names and lease files.

### Per-agent spin-up
- [ ] `git worktree add ../wt-<handle>-<task> -b agent/<handle>/<task-slug>`
- [ ] Write lease file: `_system/.locks/<handle>-<task>.lease` with TTL 45 min, renew on each tool call.
- [ ] Write directory claim: `Agent-Jobs/running/<handle>-<task>.md` listing owned paths (e.g. `src/payments/**`).
- [ ] Inject `AGENTS.md` + `.cursor/rules/*.mdc` with project conventions, the PR-merge rule, and the no-secrets rule.

### Per-task handoff
- [ ] Worker opens a draft PR; orchestrator (human or judge agent) merges only after CI green + review.
- [ ] After merge: orchestrator appends to `Handoffs/<date>-<handle>-<task>.md` and to `Project-Reports/<date>.md`.
- [ ] Lease and claim files deleted by the orchestrator, not the agent.

### End-of-session writeback
- [ ] Commit any final vault edits with `git commit -m "vault: post-merge writeback for #<task>"`.
- [ ] `git worktree remove` the worker's worktree.
- [ ] Reconcile `Project-Reports/<date>.md` with the PR list from `git log --oneline --since=today`.

### Daily / weekly hygiene
- [ ] Weekly: `git worktree list` to find orphaned worktrees; prune with `git worktree prune`.
- [ ] Weekly: verify no agent has uncommitted vault drift (`git status --porcelain` should be empty).
- [ ] Monthly: regenerate the vault from PRs (`git log --pretty=format:%H -- Agent-Jobs/`); diff against current vault.

### Hard rules
1. **One writer per file at a time.** If two agents need the same file, sequence via PR, not parallel.
2. **Vault edits only via PR merge.** No agent writes to `main` directly.
3. **TTL on every lease.** 30 min default; 90 min hard cap; renew on tool-call boundary.
4. **No secrets in vault.** Vault is human-readable and ships to humans; secrets live in env or vault.
5. **Plan before code.** Any task > 30 min agent time goes through Planner-Worker-Judge.

---

## 3.1 Alternative Topologies (when the checklist doesn't fit)

- **Tiny fleet (1-2 agents):** Drop the lease layer; one worktree, one claim file, one PR. The full ceremony is overkill.
- **Burst compute (5-10 short-lived agents):** Use Composio Agent Orchestrator or Claude Squad; their worktree-per-agent + dashboard + auto-merge pipeline replaces the manual PR step for low-risk tasks [4].
- **Long-running planner + many sub-agents:** A single planner with A2A delegation to N ephemeral workers (Cursor's `Composer 2.0` model); workers never touch the vault, only return artifacts.
- **Tracker-first, vault-second:** Linear Issues for routing + Obsidian for context. Linear Agent (June 2026) auto-fixes triage bugs and writes code [9]; pair it with the vault as the human-readable log.

---

## 4. References

1. Addy Osmani, *The Code Agent Orchestra - what makes multi-agent coding work*, O'Reilly AI CodeCon, March 26, 2026. https://addyosmani.com/blog/code-agent-orchestra/
2. Termdock, *Git Worktree for Multi-Agent Dev: Setup Guide*, March 17, 2026. https://www.termdock.com/blog/git-worktree-multi-agent-setup
3. Cursor, *Cursor Agent Best Practices 2026: Multi-File Edits, Parallel Agents & Rules*, May 11, 2026. https://baeseokjae.github.io/posts/cursor-agent-best-practices-2026
4. Tembo / Composio, *AI Agent Orchestration Tools for Coding (2026)*. https://tembo.io/blog/ai-agent-orchestration-tools
5. breferrari, *obsidian-mind: A self-organizing Obsidian vault that gives AI coding agents persistent memory*, GitHub. https://github.com/breferrari/obsidian-mind
6. Obsidian 1.12.0 changelog (CLI + Bases toolbar), Feb 10, 2026. https://obsidian.md/changelog/2026-02-10-desktop-v1.12.0
7. Linux Foundation, *A2A Protocol Surpasses 150 Organizations, Lands in Major Cloud Platforms*, April 9, 2026. https://www.linuxfoundation.org/press/a2a-protocol-surpasses-150-organizations-lands-in-major-cloud-platforms-and-sees-enterprise-production-use-in-first-year
8. AgentPatterns.ai, *AI Agent Development Anti-Patterns and Failure Modes*, 2026. https://agentpatterns.ai/anti-patterns
9. Linear, *Now - Linear writes the code, too*, June 12, 2026. https://linear.app/blog
10. CodeAgentSwarm, *Git Worktrees for AI Coding Agents: Run Multiple Agents on One Repo*, 2026. https://www.codeagentswarm.com/en/guides/git-worktrees-for-ai-coding-agents
11. NiteAgent, *Building with the 2026 Agent Protocol Stack: MCP, A2A, and the Production Architecture*, June 7, 2026. http://niteagent.com/blog/2026-06-07-agent-protocol-stack-mcp-a2a-production
12. Cursor Compile 2026, *AI-Native Development Wave*, June 18, 2026. https://eigent.ai/blog/cursor-compile-2026-ai-native-development
</answer>

## References

1. *A2A Protocol Surpasses 150 Organizations, Lands in Major ...*. https://www.linuxfoundation.org/press/a2a-protocol-surpasses-150-organizations-lands-in-major-cloud-platforms-and-sees-enterprise-production-use-in-first-year
2. *Building with the 2026 Agent Protocol Stack: MCP, A2A, and the Production Architecture*. http://niteagent.com/blog/2026-06-07-agent-protocol-stack-mcp-a2a-production
3. *MCP Shared Memory Server (junto-memory) - GitHub*. https://github.com/tlemmons/junto-memory
4. *A2A Protocol*. https://a2a-protocol.org/latest
5. *Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory | by Don Moon | Byte-Sized AI | Medium*. http://medium.com/byte-sized-ai/mem0-building-production-ready-ai-agents-with-scalable-long-term-memory-4a9d040cf8f7
6. *GitHub - breferrari/obsidian-mind: A self-organizing Obsidian vault that gives AI coding agents persistent memory. Claude Code, Codex CLI, Gemini CLI. · GitHub*. http://github.com/breferrari/obsidian-mind
7. *AI Undecided: notes from people building AI in plain English*. http://aiundecided.com/
8. *Obsidian as Your AI's Operating System: A Technical Setup Guide ...*. https://kisztof.medium.com/why-your-claude-code-setup-loses-context-every-session-and-the-obsidian-architecture-that-fixes-it-2f32b0700531
9. *jshph/enzyme-skill: Agent Skill for exploring Obsidian ...*. http://github.com/jshph/enzyme-skill
10. *Sync Obsidian Vaults | Rclone CLI*. https://rcloneui.com/docs/cli/tips/obsidian-sync
11. *Git Worktrees for AI Coding Agents: Run Multiple Agents on ...*. https://www.codeagentswarm.com/en/guides/git-worktrees-for-ai-coding-agents
12. *Git worktrees for parallel AI coding agents - Upsun Developer Center*. https://developer.upsun.com/posts/ai/git-worktrees-for-parallel-ai-coding-agents
13. *Superset IDE: Run 10 AI Coding Agents in Parallel - Noqta*. http://noqta.tn/en/blog/superset-ide-multi-agent-parallel-ai-coding-2026
14. *How to Use Git Worktrees for Parallel AI Agent Execution*. https://www.augmentcode.com/guides/git-worktrees-parallel-ai-agent-execution
15. *Git Worktrees for Parallel AI Agents: 2026 Guide - noqta.tn*. https://noqta.tn/en/blog/git-worktrees-parallel-ai-coding-agents-guide-2026
16. *Agentic orchestrator for parallel coding ...*. https://github.com/AgentWrapper/agent-orchestrator
17. *Cursor Agent Best Practices 2026: Multi-File Edits, Parallel ...*. https://baeseokjae.github.io/posts/cursor-agent-best-practices-2026
18. *AI Agent Orchestration Tools for Coding (2026) - Tembo.io*. http://tembo.io/blog/ai-agent-orchestration-tools
19. *Parallel Agent Execution via Internal Branching - Feature Requests*. https://forum.cursor.com/t/parallel-agent-execution-via-internal-branching/51060
20. *The Code Agent Orchestra - what makes multi- ...*. https://addyosmani.com/blog/code-agent-orchestra
21. *Git Worktree for Multi-Agent Dev: Setup Guide | Termdock*. https://www.termdock.com/blog/git-worktree-multi-agent-setup
22. *Mastering Git at Matillion: Uncommitted Changes*. https://www.matillion.com/blog/mastering-git-at-matillion-uncommitted-changes
23. *Parallel AI Agents with Git Worktree - Multi-Session Guide ...*. https://www.gitworktree.org/ai-tools/parallel-agents
24. *GitHub - vij1ay/agentic_dag_workflow: DAG-based agent ...*. https://github.com/vij1ay/agentic_dag_workflow
25. *Linear*. http://linkedin.com/company/linearapp
26. *GitHub - caramaschiHG/awesome-ai-agents-2026: The most ...*. https://github.com/caramaschiHG/awesome-ai-agents-2026
27. *10 Best Open Source Agent Projects to Star on GitHub (2026)*. https://flowith.io/blog/10-best-open-source-agent-projects-github-2026
28. *GitHub - bazobehram/agentic-cli: Run and coordinate multiple ...*. https://github.com/bazobehram/agentic-cli
29. *GitHub - breferrari/obsidian-mind: A self-organizing Obsidian vault that gives AI coding agents persistent memory. Claude Code, Codex CLI, Gemini CLI. · GitHub*. https://github.com/breferrari/obsidian-mind
30. *GitHub - jshph/enzyme-skill: Agent Skill for exploring Obsidian vaults with Enzyme — self-contained, cross-agent compatible · GitHub*. https://github.com/jshph/enzyme-skill
31. *Now – Updates from the Linear team*. https://linear.app/blog
32. *AI Agent Orchestration Tools for Coding (2026) – Tembo*. https://tembo.io/blog/ai-agent-orchestration-tools
33. *Cursor Compile 2026 & the AI-Native Development Wave*. http://eigent.ai/blog/cursor-compile-2026-ai-native-development
34. *Phasr: Open-Source AI Agent Workspace*. http://phasr.sh/
35. *Cursor's April 2026 Agent Mode Overhaul: Background Agents ...*. https://agentmarketcap.ai/blog/2026/04/05/cursor-april-2026-agent-mode-overhaul-background-agents-ide-convergence
36. *Obsidian Release Notes - June 2026 Latest Updates - Releasebot*. https://releasebot.io/updates/obsidian
37. *Obsidian 1.9.0 Desktop (Early access)*. https://obsidian.md/changelog/2025-05-21-desktop-v1.9.0
38. *Obsidian 1.12.0 Desktop (Early access) - Obsidian*. https://obsidian.md/changelog/2026-02-10-desktop-v1.12.0
39. *Obsidian Plugin Updates: A Safe 2026 Workflow | Obsibrain*. https://www.obsibrain.com/blog/obsidian-plugin-updates-safe-workflow
40. *Bases release date : r/ObsidianMD*. https://www.reddit.com/r/ObsidianMD/comments/1lhyw6u/bases_release_date
41. *Git Worktree for AI Agents: Enabling Parallel Development ...*. https://docs.bswen.com/blog/2026-03-30-git-worktree-ai-agents
42. *Git Worktree Isolation Patterns for Parallel AI Agent ...*. https://zylos.ai/en/research/2026-02-22-git-worktree-parallel-ai-development
43. *Git Worktrees for AI Coding Agents: Full Guide - Nimbalyst*. https://nimbalyst.com/blog/git-worktrees-for-ai-coding-agents-complete-guide
44. *Git Worktree Conflicts with Multiple AI Agents: Diagnosis and Fixes*. https://www.termdock.com/en/blog/git-worktree-conflicts-ai-agents
45. *Git worktrees: work on multiple branches simultaneously*. http://blog.stackademic.com/git-worktrees-work-on-multiple-branches-simultaneously-5774ef6db341
46. *Anti-Patterns in Multi-Agent Gen AI Solutions: Enterprise ...*. https://medium.com/data-science-collective/anti-patterns-in-multi-agent-gen-ai-solutions-enterprise-pitfalls-and-best-practices-ea39118f3b70
47. *Anti-Pattern Multi-Agent Overkill: Too Many Agents in the System*. https://www.agentpatterns.tech/en/anti-patterns/multi-agent-overkill
48. *AI Agent Development Anti-Patterns and Failure Modes - AgentPatterns.ai*. http://agentpatterns.ai/anti-patterns
49. *MCP/Skills Anti-Pattern Collection | AI Agent Architecture*. https://shuji-bonji.github.io/ai-agent-architecture/skills/anti-patterns
50. *Agent Patterns for AI Agent Development — AgentPatterns.ai*. http://agentpatterns.ai/
