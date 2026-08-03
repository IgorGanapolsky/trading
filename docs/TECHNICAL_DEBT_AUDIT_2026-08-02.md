# Technical debt audit — 2026-08-02

## Status

Implementation, merge, and post-merge validation are complete. [PR #4328](https://github.com/IgorGanapolsky/trading/pull/4328) was squash-merged as `0efb9bda4c06d950f0a153b7a41e6b360917fa74`. Fresh `main` CI, Main Head Verification, CodeQL, Offline Evals, OpenSSF, and SonarCloud all passed on that exact SHA. The credential-free paper dry run failed closed before broker access, so authenticated inventory validation remains a separate proof surface.

Audit baseline: `ae7dc2a5213ec77769fc4a5e56caf86ac25d0d10`

Coordination issue: [IGO-35](https://linear.app/igorganapolsky/issue/IGO-35/trading-repo-comprehensive-cleanup-and-coordination-hardening)

## Executive results

```text
Files scanned: 2,953 baseline tracked files; 1,146 retained files rescanned
Issues found: 2,654 bounded path/check findings
Issues fixed: 2,654 bounded path/check findings
Files deleted: 1,842
Lines removed: 214,552 Git text deletions; final physical-line delta below
RAG entries cleaned: 146 net lesson-file reduction
```

The reproducible issue count is 1,842 removable tracked paths + 798 Ruff findings + 5 high-confidence weak-hash findings + 4 high npm advisories + 1 failing baseline test + 1 stale/yanked lock entry + 3 judge-panel isolation/redaction defects found in the final concurrent `main` merge. Broader architectural gaps are reported separately and are not hidden inside this number.

## Before and after

| Metric                            |        Before |                     After |    Delta |
| --------------------------------- | ------------: | ------------------------: | -------: |
| Tracked files                     |         2,953 |                     1,146 |   -1,807 |
| Physical lines scanned            |     1,244,491 |                   272,156 | -972,335 |
| SCC code lines                    |       346,527 |                   199,232 | -147,295 |
| Python code lines (SCC)           |       157,903 |                   140,721 |  -17,182 |
| GitHub workflow files             |            83 |                        24 |      -59 |
| RAG lesson files                  |           318 |                       172 | -146 net |
| Full-suite failures               |             1 |                         0 |       -1 |
| Python dependency vulnerabilities | not baselined |                   0 known |    clean |
| npm high advisories               |             4 | 0 Node subsystem retained |       -4 |

Git comparison: [baseline to merged audit SHA](https://github.com/IgorGanapolsky/trading/compare/ae7dc2a5213ec77769fc4a5e56caf86ac25d0d10...0efb9bda4c06d950f0a153b7a41e6b360917fa74). Its Files view is the exact deleted-file list; the groups below explain why each class was removed.

## Deleted paths and justification

| Group                                                                                     | Evidence and justification                                                                                |
| ----------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| Generated screenshots, snapshots, reports, audit dumps, caches, logs, and `graphify-out/` | Rebuildable output with no source ownership; ignored and guarded by hygiene tests                         |
| Trigger.dev/Node experiment                                                               | No retained caller; removal also eliminated four high npm advisories                                      |
| Stale iron-condor entry workflows and scripts                                             | Current kill switch permits paper SPY put-credit entry and residual IC exits only                         |
| Ralph/CCPM/duplicate `.claude` frameworks                                                 | No current workflow or import callers; displaced task management now lives in Linear                      |
| Browser automation, contest, sales, pitch, and copied documentation artifacts             | Outside the retained trading runtime or duplicated canonical docs                                         |
| Disabled RAG webhook deployment files and generated indexes                               | No active deploy owner; query index is rebuilt from curated source lessons                                |
| Zero-caller `src/markets/option_chain.py`                                                 | IC-only selector had 0% coverage, no callers, and was the sole cause of a stale critical-coverage failure |
| Redundant requirements/configuration and stale `.env.example` keys                        | Consolidated under `pyproject.toml`, `uv.lock`, and a minimal secret-free environment contract            |
| Contradictory or duplicate RAG lessons                                                    | Superseded operational claims removed or consolidated; duplicate-content scan is now zero                 |

No user-owned dirty primary-checkout changes or other agents' active worktrees were deleted.

## Refactored and hardened surfaces

- `scripts/audit_repository_hygiene.py`: scans every retained candidate path and every text line; detects generated paths, user-specific absolute paths, malformed workflows, duplicate RAG content/IDs, and stale lesson states.
- `scripts/query_lessons_learned.py`: restored dependency-free query CLI with keyword fallback and JSON output.
- `scripts/system_health_check.py` and RAG health path: bounded keyword query plus isolated read/write proof.
- `src/agents/rag_webhook.py`: side-effect-free import and current UTC handling.
- `src/evals/judge_panel/`: deterministic claim/PR/coordination audit with credential redaction, isolated foreign-agent evidence, complete Grok collision detection, and trade-entry refusal.
- `scripts/spy_put_credit.py` + `scripts/residual_ic_manager.py`: documented as the only current entry/exit owners.
- GitHub workflows: removed ownerless schedules, bounded permissions/triggers, forced manual validation to dry-run, changed CodeQL from JavaScript to Go, and added workflow dependency contracts.
- `pyproject.toml`, `uv.lock`, `.trunk/trunk.yaml`, and `Makefile`: one Python contract, hermetic Go/Python tool versions, security checks, and one `make check` path.
- `README.md`, `docs/README.md`, `docs/operator-guide.md`, `skills/trading-ops/SKILL.md`, and `docs/AGENT_COORDINATION.md`: Herdr-inspired pitch/docs/skill layout with current operational truth.

## Test coverage

```text
Before: 63.445% on a smaller historical source scope (not comparable)
After: 51.7203% combined src + scripts statement-and-branch coverage
New tests: query CLI, repository hygiene, workflow dependencies/contracts, docs/skill layout, RAG health, import safety, and runtime isolation
```

The final local CI-equivalent run contained 3,112 passing tests, 30 skips, 1 expected failure, and 0 failures across the core and integration phases. Coverage measured 50,851 statements and 14,866 branches: 27,470 statements and 6,519 branches were covered. The combined coverage floor is now enforced at 50%; all six critical-file thresholds passed.

Remaining coverage gaps are real:

- `src/orchestrator/main.py` and `src/orchestrator/gates.py` remain below 40%.
- `scripts/system_health_check.py` remains below 40%.
- Several optional research/provider and explicit emergency operator commands have 0% coverage.
- Broker execution modules remain mixed, with high-risk paths protected by gates but not 100% branch-covered.

The prior 63.445% value covered 21,322 of 33,607 statements on a narrower source set, so presenting it as a before/after regression would be misleading.

## Security and dependency health

- `pip-audit`: no known vulnerabilities in the resolved Python environment.
- Bandit high severity/high confidence: zero after replacing five SHA-1/MD5 fingerprints with SHA-256.
- `google-auth`: yanked 2.46.0 lock entry upgraded to 2.56.2.
- `uv lock --check`: clean.
- Secret scan: remaining matches reviewed as content hashes, RAG IDs, environment-variable names, test fixtures, or prose; no stored credential value was identified.
- Go 1.25 hermetic suite: passing.

## Protected-system verification

| Component               | Local proof                                                                                       | GitHub proof                                                                                                                                                                     |
| ----------------------- | ------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| AI RAG read/query/write | bounded health loaded 172 lessons, returned queries, and passed an isolated write/read round-trip | [Main Head Verification passed](https://github.com/IgorGanapolsky/trading/actions/runs/30783436103)                                                                              |
| Python orchestration    | 145 focused RAG/orchestrator/health tests plus the full suite passed                              | [Main CI passed](https://github.com/IgorGanapolsky/trading/actions/runs/30783436135)                                                                                             |
| Go orchestration        | `go test ./...` passing with hermetic Go 1.25                                                     | [Main CI](https://github.com/IgorGanapolsky/trading/actions/runs/30783436135) and [CodeQL passed](https://github.com/IgorGanapolsky/trading/actions/runs/30783436143)            |
| Monitoring              | bounded health passed; workflow contracts and self-healing tests passed                           | [Main Head Verification passed](https://github.com/IgorGanapolsky/trading/actions/runs/30783436103)                                                                              |
| CI pipeline             | full local runner, Ruff, workflow integrity, dependency audit, Bandit, and repository audit pass  | [PR checks](https://github.com/IgorGanapolsky/trading/actions/runs/30782501761) and [fresh `main` CI](https://github.com/IgorGanapolsky/trading/actions/runs/30783436135) passed |

## CI health

```text
Pipeline status: PASSING on merged SHA 0efb9bda4c06d950f0a153b7a41e6b360917fa74
Flaky tests fixed: baseline failure plus CI test-isolation failures
New checks: repository hygiene, workflow dependency integrity, docs/skill layout, security target, combined branch coverage
```

Fresh post-merge evidence:

- [Full `main` CI](https://github.com/IgorGanapolsky/trading/actions/runs/30783436135): passed, including workflow validation, Trunk, changed-path detection, and the full test runner.
- [Main Head Verification](https://github.com/IgorGanapolsky/trading/actions/runs/30783436103): passed bounded health and the generated-state regression ring.
- [SonarCloud](https://github.com/IgorGanapolsky/trading/actions/runs/30783436102): coverage generation and scan passed.
- [CodeQL](https://github.com/IgorGanapolsky/trading/actions/runs/30783436143), [Offline Evals](https://github.com/IgorGanapolsky/trading/actions/runs/30783436108), and [OpenSSF Scorecard](https://github.com/IgorGanapolsky/trading/actions/runs/30783436137): passed.

The local paper command reached the broker-inventory boundary and failed closed because Alpaca paper credentials were not present in the isolated worktree. No order was submitted. This is safe fail-closed evidence, not authenticated broker or dry-run success.

An older scheduled `main` failure was traced to the now-deleted `automated-system-hygiene.yml`: it installed pytest without `pytest-cov` and exercised obsolete IC/SciPy test state. The cleanup does not call that run green; only fresh PR and post-merge runs establish the final CI status.

## Coordination outcome

The adopted contract is deliberately layered:

- Herdr: live terminal topology and agent lifecycle.
- Linear: durable issue ownership.
- Shared Obsidian vault: live file/WIP claim and handoff.
- Worktree/PR: authoritative code state.

The Obsidian Linear community plugin remains an optional human dashboard. It is not used as a concurrency lock and the trading repository does not duplicate the shared Linear bridge.

## Residual debt and follow-up

1. Ratchet combined coverage from the verified floor toward 70%, prioritizing orchestrator gates, system health, and broker boundaries.
2. Review the active `eval-engineering-hiroi` orphan branch separately; it contains a large unique evaluation pipeline and was preserved rather than deleted.
3. Classify the newly generated `auto/self-heal-*` branch after its owner/run settles; it is active, not stale.
4. Follow-up [AGENT-26](https://linear.app/igorganapolsky/issue/AGENT-26/trading-follow-up-coverage-ratchet-and-authenticated-paper-dry-run) records the coverage ratchet, authenticated paper dry run, and preserved-branch reclassification work.
5. Re-run the paper inventory dry run in an authenticated environment; the isolated worktree proved fail-closed behavior only.
