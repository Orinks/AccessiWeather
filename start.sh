#!/bin/bash

# AccessiWeather Development Startup Script
# This script starts the AccessiWeather application in development mode using Briefcase

set -e  # Exit on any error

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="$PROJECT_DIR/.venv"

echo "Starting AccessiWeather development server..."
echo "Project directory: $PROJECT_DIR"

# Change to project directory
cd "$PROJECT_DIR"

# Check if virtual environment exists
if [ ! -d "$VENV_PATH" ]; then
    echo "Error: Virtual environment not found at $VENV_PATH"
    echo "Please create a virtual environment first by running:"
    echo "  uv venv"
    echo "  uv pip install -e ."
    exit 1
fi

# Activate virtual environment
echo "Activating virtual environment..."
# For Windows environments (Git Bash, MSYS2), always use Scripts directory
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || -d "$VENV_PATH/Scripts" ]]; then
    # Windows (Git Bash, MSYS2, or Cygwin)
    source "$VENV_PATH/Scripts/activate"
else
    # Unix-like systems (Linux, macOS)
    source "$VENV_PATH/bin/activate"
fi

# Check if briefcase is installed
if ! command -v briefcase &> /dev/null; then
    echo "Installing briefcase..."
    uv pip install briefcase
fi

# Check if the app is configured for briefcase
if [ ! -f "pyproject.toml" ]; then
    echo "Error: pyproject.toml not found. This doesn't appear to be a Briefcase project."
    exit 1
fi

echo "Starting AccessiWeather in development mode..."
echo "Press Ctrl+C to stop the application"
echo ""

# Start the application in development mode
briefcase dev
