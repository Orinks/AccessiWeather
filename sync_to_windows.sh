#!/bin/bash
# Sync BMAD and project files from WSL to Windows

# Configuration
WSL_PROJECT="/home/josh/accessiweather"
WINDOWS_PROJECT="/mnt/c/Users/$USER/accessiweather"  # Adjust this path!

echo "Syncing from WSL to Windows..."
echo "Source: $WSL_PROJECT"
echo "Target: $WINDOWS_PROJECT"

# Create Windows directory if it doesn't exist
mkdir -p "$WINDOWS_PROJECT"

# Sync .bmad folder
echo "Syncing .bmad folder..."
rsync -av --delete \
    --exclude='.bmad-user-memory/' \
    --exclude='*.pyc' \
    --exclude='__pycache__/' \
    "$WSL_PROJECT/.bmad/" \
    "$WINDOWS_PROJECT/.bmad/"

# Sync source code and configs
echo "Syncing source files..."
rsync -av --delete \
    --exclude='venv/' \
    --exclude='.venv/' \
    --exclude='.briefcase/' \
    --exclude='build/' \
    --exclude='dist/' \
    --exclude='*.pyc' \
    --exclude='__pycache__/' \
    --exclude='.git/' \
    "$WSL_PROJECT/src/" \
    "$WINDOWS_PROJECT/src/"

# Sync important config files
echo "Syncing config files..."
rsync -av \
    "$WSL_PROJECT/pyproject.toml" \
    "$WSL_PROJECT/README.md" \
    "$WSL_PROJECT/.gitignore" \
    "$WINDOWS_PROJECT/"

# Sync docs
echo "Syncing docs..."
rsync -av --delete \
    "$WSL_PROJECT/docs/" \
    "$WINDOWS_PROJECT/docs/"

echo "✅ Sync complete!"
echo ""
echo "To test on Windows:"
echo "1. Open Windows Terminal or PowerShell"
echo "2. cd $WINDOWS_PROJECT"
echo "3. briefcase dev"
