#!/bin/bash
# WorktreeRemove hook — push any unpushed commits as a safety net
# Claude Code should have already created the PR; this just ensures the branch is pushed.

BRANCH=$(git -C "$WORKTREE_PATH" branch --show-current 2>/dev/null)

if [ -n "$BRANCH" ] && [ "$BRANCH" != "main" ] && [ "$BRANCH" != "dev" ]; then
  git -C "$WORKTREE_PATH" push origin "$BRANCH" --quiet 2>/dev/null || true
  echo "[worktree-remove] Pushed $BRANCH"
fi
