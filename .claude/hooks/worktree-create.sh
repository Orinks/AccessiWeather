#!/bin/bash
# WorktreeCreate hook — rebase new worktree onto dev (or main if no dev branch)
set -e

cd "$WORKTREE_PATH"

git fetch origin --quiet

if git show-ref --verify --quiet refs/remotes/origin/dev; then
  git reset --hard origin/dev
  echo "[worktree-create] Rebased to origin/dev"
else
  git reset --hard origin/main
  echo "[worktree-create] No dev branch found, rebased to origin/main"
fi
