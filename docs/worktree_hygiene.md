## Worktree Hygiene

### CLI
- One-off check (non-destructive):
  - `scripts/worktree_hygiene.sh`
- Prune stale entries (safe):
  - `scripts/worktree_hygiene.sh --prune`
- Remove detached worktrees (force):
  - `scripts/worktree_hygiene.sh --remove-detached`

### Local CI integration
`scripts/run_local_ci.sh` now calls `scripts/worktree_hygiene.sh` at the start, so every local CI run reports the current worktree state and prunes if you pass the flags manually.

### Scheduled (cron) cleanup
Use `scripts/worktree_hygiene_cron.sh` to prune and remove detached worktrees automatically.

Suggested cron (runs weekly, Sunday 03:15):

```cron
15 3 * * Sun cd /Users/ganapolsky_i/workspace/git/igor/trading && scripts/worktree_hygiene_cron.sh >> logs/worktree_hygiene.log 2>&1
```

Adjust the path if your repo root differs. The script is idempotent and safe to run more frequently if desired.

### macOS launchd (preferred over cron)
1) Install/load job:
```bash
scripts/install_worktree_launchd.sh
```
This writes `~/Library/LaunchAgents/com.trading.worktreehygiene.plist`, sets the repo path and log path (`~/Library/Logs/worktree_hygiene.log`), and loads it. It runs daily at 03:15 and at load.

2) Logs: `tail -f ~/Library/Logs/worktree_hygiene.log`

### Log rotation
`scripts/worktree_hygiene_cron.sh` now rotates `logs/worktree_hygiene.log` (or `LOG_FILE`) keeping the last 10 archives to prevent bloat.

### Slack digest (optional)
Send the latest hygiene log to Slack:
```bash
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/XXX \
LOG_FILE=logs/worktree_hygiene.log \
scripts/worktree_hygiene_digest.sh
```

### Strict gate in local CI
Set `STRICT_HYGIENE=1 ./scripts/run_local_ci.sh` to fail fast if any detached worktrees exist. Default is soft (warn only).
