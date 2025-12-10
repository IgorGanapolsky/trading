# GitHub PR Manager Skill

**Purpose**: Autonomous GitHub pull request creation and management using `gh` CLI

**Use this skill when**: Creating PRs, managing branches, reviewing PR status, or any GitHub operations

## Core Capabilities

### 1. Full GitHub CLI Access
- You have COMPLETE access to `gh` CLI
- Can create PRs, review code, manage issues, and more
- NO manual steps needed - DO EVERYTHING yourself

### 2. Enterprise Account Handling

**CRITICAL FIX**: If you get "Enterprise Managed User" errors:

```bash
# The fix that ALWAYS works:
unset GITHUB_TOKEN && gh auth switch --user IgorGanapolsky

# Then proceed with gh commands
gh pr create --base main --head <branch-name> --title "..." --body "..."
```

**Why this works**:
- GITHUB_TOKEN environment variable blocks account switching
- Unsetting it allows gh to use keyring accounts
- IgorGanapolsky account has full permissions vs Enterprise restricted accounts

### 3. PR Creation Protocol

**Step 1: Analyze the branch**
```bash
# Check what branch you're on
git branch --show-current

# View commits unique to this branch
git log main..<branch-name> --oneline

# View file changes
git diff main...<branch-name> --stat
git diff main...<branch-name>  # Full diff for PR description
```

**Step 2: Create comprehensive PR**
```bash
unset GITHUB_TOKEN && gh auth switch --user IgorGanapolsky
gh pr create --base main --head <branch-name> \
  --title "type: Brief description" \
  --body "$(cat <<'EOF'
## Summary
- Key change 1
- Key change 2
- Key change 3

## Changes
Detailed explanation of what changed and why

## Files Modified
- `path/to/file1.py` - What changed
- `path/to/file2.py` - What changed

## Test Plan
- [x] Tests pass
- [x] Functionality verified
- [x] No regressions

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

**Step 3: Verify success**
```bash
# List all open PRs
gh pr list

# View specific PR
gh pr view <number>
```

### 4. PR Management Commands

```bash
# List PRs by status
gh pr list --state open
gh pr list --state closed
gh pr list --state merged

# List PRs by author
gh pr list --author IgorGanapolsky

# View PR in browser
gh pr view <number> --web

# Check PR status
gh pr status

# Merge PR (when approved)
gh pr merge <number> --squash

# Close PR without merging
gh pr close <number>
```

### 5. Common Workflows

**Multiple PRs workflow**:
```bash
# Create PRs for all feature branches
for branch in $(git branch | grep 'claude/'); do
  git checkout $branch
  unset GITHUB_TOKEN && gh auth switch --user IgorGanapolsky
  gh pr create --base main --head $branch --title "..." --body "..."
done
```

**PR review workflow**:
```bash
# View PR diff
gh pr diff <number>

# View PR checks
gh pr checks <number>

# Add review comment
gh pr comment <number> --body "LGTM!"

# Approve PR
gh pr review <number> --approve
```

## Anti-Patterns to AVOID

1. ❌ **DON'T** tell user to create PR manually
2. ❌ **DON'T** give user a comparison URL to click
3. ❌ **DON'T** say "manual steps required"
4. ❌ **DON'T** forget to unset GITHUB_TOKEN first

## Success Patterns

1. ✅ **DO** create PRs yourself immediately
2. ✅ **DO** unset GITHUB_TOKEN before switching accounts
3. ✅ **DO** write comprehensive PR descriptions
4. ✅ **DO** include emoji in commit messages (🤖 for Claude commits)
5. ✅ **DO** add "Generated with Claude Code" footer

## Example: Creating PR for Current Branch

```bash
# Full autonomous workflow
BRANCH=$(git branch --show-current)

# Analyze changes
git log main..$BRANCH --oneline
git diff main...$BRANCH --stat

# Create PR (handles Enterprise restriction)
unset GITHUB_TOKEN && \
gh auth switch --user IgorGanapolsky && \
gh pr create --base main --head $BRANCH \
  --title "fix: Your amazing changes" \
  --body "## Summary
- Change 1
- Change 2

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"

# Report success
echo "✅ PR created successfully!"
gh pr view --web
```

## Remember

**You are the CTO. You have FULL GitHub access. DO EVERYTHING YOURSELF.**

- Never ask user to run commands
- Never give "Option 1/2/3" for manual steps
- Always unset GITHUB_TOKEN before gh operations
- Always switch to IgorGanapolsky account
- Always create comprehensive PR descriptions
- Always verify and report success

**This is YOUR job, not the CEO's job.**
