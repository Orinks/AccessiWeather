#!/usr/bin/env bash
# bootstrap-worktree.sh — Set up a fresh worktree for development or agent use.
# Usage: bash scripts/bootstrap-worktree.sh [worktree-path]
# If no path given, bootstraps the current directory.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${1:-$SCRIPT_DIR/..}"
TARGET="$(realpath "$TARGET")"

echo "Bootstrapping: $TARGET"

# 1. Create venv if missing
if [ ! -d "$TARGET/.venv" ]; then
  echo "Creating venv..."
  uv venv "$TARGET/.venv" --python 3.12
else
  echo "Venv already exists, skipping."
fi

# 2. Install deps
echo "Installing dependencies..."
uv pip install \
  --python "$TARGET/.venv/bin/python" \
  -e "$TARGET[dev]" \
  --no-binary wxPython \
  --find-links https://extras.wxpython.org/wxPython4/extras/linux/gtk3/ubuntu-22.04/

# 3. Install pre-commit hook
echo "Installing pre-commit hook..."
cd "$TARGET"
pre-commit install 2>/dev/null || echo "pre-commit not available, skipping."

echo ""
echo "Done. Activate with:"
echo "  source $TARGET/.venv/bin/activate"
echo ""
echo "Run tests with:"
echo "  $TARGET/.venv/bin/pytest"
