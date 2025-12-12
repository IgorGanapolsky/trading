# Create and Merge PR

Create a PR for the current branch and merge it autonomously.

## Prerequisites
- Changes committed to a feature branch (not main)
- GitHub PAT available (provided by CEO at runtime)

## Procedure

### 1. Create PR via GitHub API
```bash
curl -X POST \
  -H "Authorization: token $GITHUB_PAT" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/IgorGanapolsky/trading/pulls \
  -d '{"title": "type: description", "head": "<branch>", "base": "main", "body": "## Summary\n..."}'
```

### 2. Run Pre-Merge Gate
```bash
python3 scripts/pre_merge_gate.py
```

### 3. Merge PR via GitHub API
```bash
curl -X PUT \
  -H "Authorization: token $GITHUB_PAT" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/IgorGanapolsky/trading/pulls/<PR_NUMBER>/merge \
  -d '{"merge_method": "squash", "commit_title": "type: description (#PR_NUMBER)"}'
```

### 4. Post-Merge Verification
```bash
python3 -c "from src.orchestrator.main import TradingOrchestrator; print('OK')"
```

## Fallback (gh CLI)
```bash
export GH_TOKEN=$GITHUB_PAT
gh pr create --base main --head <branch> --title "type: description" --body "..."
gh pr merge <PR_NUMBER> --squash --delete-branch
```

## Rules
- NEVER store PAT in any file
- NEVER ask CEO to create/merge PRs - do it yourself
- Complete full lifecycle in one session: create → merge → cleanup
