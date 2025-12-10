#!/usr/bin/env bash
set -euo pipefail

# Simple hygiene utility for git worktrees.
# Default: read-only (reports only). Use flags to prune or remove detached worktrees.
#
# Usage:
#   scripts/worktree_hygiene.sh          # show status / warnings
#   scripts/worktree_hygiene.sh --prune  # prune missing/stale worktrees (safe)
#   scripts/worktree_hygiene.sh --remove-detached  # remove detached worktrees (force)
#
# Recommended to run weekly or before adding a new worktree.

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

do_prune=false
remove_detached=false

for arg in "$@"; do
  case "$arg" in
    --prune) do_prune=true ;;
    --remove-detached) remove_detached=true ;;
    *)
      echo "Unknown option: $arg"
      echo "Usage: $0 [--prune] [--remove-detached]"
      exit 1
      ;;
  esac
done

echo "📂 Repo: $repo_root"
echo "➕ Listing worktrees:"
git worktree list
echo

detached_paths=()
while IFS= read -r line; do
  # porcelain format: path\nHEAD sha\nbranch ref|detached\n...
  if [[ "$line" == "worktree "* ]]; then
    current_path="${line#worktree }"
  elif [[ "$line" == "detached"* ]]; then
    detached_paths+=("$current_path")
  fi
done < <(git worktree list --porcelain)

if (( ${#detached_paths[@]} )); then
  echo "⚠️  Detached worktrees detected:"
  printf ' - %s\n' "${detached_paths[@]}"
else
  echo "✅ No detached worktrees."
fi
echo

if $do_prune; then
  echo "🧹 Pruning stale worktrees (safe)..."
  git worktree prune
  echo "✅ Prune complete."
  echo
fi

if $remove_detached && (( ${#detached_paths[@]} )); then
  echo "🗑️  Removing detached worktrees (force)..."
  for path in "${detached_paths[@]}"; do
    echo " - removing $path"
    git worktree remove --force "$path"
  done
  echo "✅ Detached worktrees removed."
fi

echo "Done."
