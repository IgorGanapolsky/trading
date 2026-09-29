---
name: jules-coordination
description: Coordinate with Google Jules cloud coding agent via official REST API, MCP server tools, and Chrome Browser Automation Bridge.
---

# Google Jules Agent Coordination & Integration

## 1. Overview & Architecture

**Google Jules** (`jules.google.com`) is Google's asynchronous cloud coding agent designed to run in isolated cloud VM containers, analyze repositories, execute test runners, and submit pull requests via GitHub App `google-labs-jules[bot]`.

In this repository ecosystem (`IgorGanapolsky/trading`), we operate a multi-agent hierarchy:
- **Antigravity / Lead Agent**: Operates locally on macOS, owns architectural safety gates, risk controls, and system hygiene.
- **Google Jules**: Cloud background worker delegated to isolate flaky tests, perform large refactors, or optimize performance.
- **Jules Browser Bridge**: Automated programmatic interface (`scripts/jules_browser_bridge.py`) utilizing authenticated Google SSO (`iganapolsky@gmail.com`) to extract proactive suggestions, inspect code context, and dispatch cloud jobs.

```
                             MULTI-AGENT ARCHITECTURE WITH JULES
                             
  ┌─────────────────────────┐                     ┌───────────────────────────┐
  │   Antigravity / Local   │◄─── Browser Bridge ─►│  Google Chrome Tab (SSO)  │
  │   Operator (macOS)      │   (AppleScript JS)  │  (jules.google.com)       │
  └───────────┬─────────────┘                     └─────────────┬─────────────┘
              │                                                 │
              │ Git / GitHub CLI                                │ Cloud VM Sandbox
              ▼                                                 ▼
  ┌─────────────────────────┐                     ┌───────────────────────────┐
  │  GitHub Repository      │◄─── PRs / Branches ─┤  Google Jules Cloud VM    │
  │  (IgorGanapolsky/       │    (google-labs-    │  (jules.googleapis.com)   │
  │   trading)              │     jules[bot])     │  Sandbox Container        │
  └─────────────────────────┘                     └───────────────────────────┘
```

---

## 2. Jules Browser Automation Bridge (`scripts/jules_browser_bridge.py`)

The repository includes a dedicated zero-dependency CLI tool to control Jules directly via Google Chrome with active Google SSO.

### A. Health Check
Verify active connection to Jules tab:
```bash
scripts/jules_browser_bridge.py health
```

### B. List Suggestions
List proactive suggestions from Jules across categories (`all`, `performance`, `security`, `code_health`, `testing`, `cleanup`):
```bash
scripts/jules_browser_bridge.py list --filter performance
scripts/jules_browser_bridge.py list --filter security --json
```

### C. Show Suggestion Details
Inspect file location, description, rationale, and code context for any suggestion index:
```bash
scripts/jules_browser_bridge.py show 24
```

### D. Dispatch Suggestion to Cloud Runner
Load suggestion into the composer, automatically inject test-isolation and safety rules, and launch the cloud job:
```bash
scripts/jules_browser_bridge.py start 20 --instructions "Prioritize zero disk I/O latency"
```

### E. List Recent Sessions
List all active and recent cloud coding sessions with IDs and status:
```bash
scripts/jules_browser_bridge.py sessions
```

---

## 3. The Test Isolation Rule (Lessons from Session 4995586535341526337)

### The Contamination Root Cause
In Jules session `4995586535341526337`, Jules executed `pytest` in its cloud container. The test `test_arxiv_collector.py` ran with a default `DocumentIngestionPipeline()`, which wrote test paper entries into `data/audit/ingestion_version_manifest.json` pointing to container ephemeral paths:
```json
"file_path": "/tmp/pytest-of-jules/pytest-93/test_ingest_paper_writes_rag_a0/rag_knowledge/arxiv/arxiv_2608_99999v1.md"
```
When Jules committed its changes, `data/audit/ingestion_version_manifest.json` was staged and pushed to remote, creating immediate merge conflicts with `origin/main`.

### Enforcement Rule
1. **Never write test artifacts to repository manifests**: Whenever a test exercises ingestion or manifest tracking, it **must** inject a sandbox manifest path using `tmp_path`.
2. `ArxivCollector` automatically isolates `self.ingestion_pipeline` whenever a non-default manifest is supplied:
   ```python
   if manifest_file is not None and manifest_file != ARXIV_MANIFEST_FILE:
       isolated_manifest = manifest_file.parent / "ingestion_version_manifest.json"
       self.ingestion_pipeline = DocumentIngestionPipeline(manifest_file=isolated_manifest)
   ```

---

## 4. Jules PR Harmonization Runbook

When Jules opens a PR (e.g. PR #4981):

1. **Inspect Branch Diff**:
   ```bash
   git fetch origin
   git diff origin/main...origin/<jules-branch> -- data/audit/ingestion_version_manifest.json
   ```

2. **Sanitize Dirty Manifests**:
   If dirty `/tmp/pytest-of-jules` entries or merge conflicts are detected:
   ```bash
   git checkout -B work/sanitize-<jules-branch> origin/<jules-branch>
   git checkout origin/main -- data/audit/ingestion_version_manifest.json
   git commit -m "chore: strip ephemeral Jules test manifest artifacts"
   ```

3. **Rebase onto current `origin/main`**:
   ```bash
   git rebase origin/main
   ```

4. **Verify Local Gates**:
   ```bash
   make check
   ```

5. **Push Sanitized Branch to Remote**:
   ```bash
   git push origin work/sanitize-<jules-branch>:<jules-branch> --force-with-lease
   ```

6. **Agent Contract Validation**:
   Ensure `src/coordination/agent_contract.py` recognizes `google-labs-jules` so CI checks succeed without blocking on manual Linear claims.
