#!/usr/bin/env bash
# Land staged GitHub Actions changes as a PR.
# Protected main cannot be pushed (GH013 / required status checks).
# Usage: scripts/land_github_actions_pr.sh <slug> <commit-message> <pr-title>
set -euo pipefail

if [[ $# -lt 3 ]]; then
	echo "Usage: $0 <slug> <commit-message> <pr-title>" >&2
	exit 2
fi

SLUG="$1"
MSG="$2"
TITLE="$3"

if git diff --staged --quiet; then
	echo "No staged changes to land"
	exit 0
fi

git config user.name "github-actions[bot]"
git config user.email "github-actions[bot]@users.noreply.github.com"

RUN_ID="${GITHUB_RUN_ID:-$(date -u +%Y%m%d%H%M%S)}"
ATTEMPT="${GITHUB_RUN_ATTEMPT:-1}"
BRANCH="chore/auto-${SLUG}-${RUN_ID}-${ATTEMPT}"

case "${TITLE}" in
*[Aa][Uu][Tt][Oo]*) ;;
*) TITLE="${TITLE} [auto]" ;;
esac

git checkout -B "${BRANCH}"
git commit -m "${MSG}"
git push -u origin "HEAD:refs/heads/${BRANCH}"

if ! command -v gh >/dev/null 2>&1; then
	echo "gh CLI missing after pushing ${BRANCH}" >&2
	exit 1
fi

REPO="${GITHUB_REPOSITORY-}"
PR_ARGS=()
if [[ -n ${REPO} ]]; then
	PR_ARGS+=(--repo "${REPO}")
fi

EXISTING="$(gh pr list "${PR_ARGS[@]}" --head "${BRANCH}" --json number --jq '.[0].number // empty')"
if [[ -n ${EXISTING} ]]; then
	echo "PR already exists for ${BRANCH}: #${EXISTING}"
	exit 0
fi

BODY="Automated state-writer landing. Main is ruleset-protected, so this PR is the only legal land path. No orders."

gh pr create "${PR_ARGS[@]}" \
	--base main \
	--head "${BRANCH}" \
	--title "${TITLE}" \
	--body "${BODY}"

gh pr merge "${PR_ARGS[@]}" --squash --auto --delete-branch ||
	echo "auto-merge not armed; PR left open for required checks"
