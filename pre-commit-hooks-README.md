# AccessiWeather Pre-commit Hooks

## Overview

This project uses pre-commit hooks to ensure code quality and consistent formatting. The hooks are configured to work in a headless environment and include special checks to ensure tests don't rely on GUI dialogs without proper mocking.

## Setup

To set up the pre-commit hooks:

1. Install pre-commit:
   ```bash
   pip install pre-commit
   ```

2. Install the hooks in your local repository:
   ```bash
   pre-commit install
   ```

## Included Hooks

### Standard Hooks
- **trailing-whitespace**: Removes trailing whitespace
- **end-of-file-fixer**: Ensures files end with a newline
- **check-yaml**: Validates YAML files
- **check-added-large-files**: Prevents large files from being committed
- **check-ast**: Ensures Python files are valid syntax
- **check-json**: Validates JSON files
- **check-merge-conflict**: Checks for merge conflict strings
- **detect-private-key**: Prevents committing private keys

### Code Quality Hooks
- **flake8**: Lints Python code
- **isort**: Sorts imports
- **black**: Formats Python code
- **mypy**: Performs static type checking

### Custom Hooks
- **headless-test-check**: Ensures tests don't use GUI dialogs without mocking

## Headless Environment Considerations

The custom `headless-test-check` hook is specifically designed to catch tests that might fail in a headless CI environment. It checks for:

- Direct calls to `wx.MessageBox()` without mocking
- Calls to `.ShowModal()` (which would display a dialog) without mocking

These checks help ensure that tests will run successfully in the GitHub Actions workflow, which uses a virtual framebuffer (Xvfb) instead of a real display.

## Bypassing Hooks

If you need to bypass the pre-commit hooks for a specific commit (not recommended):

```bash
git commit -m "Your message" --no-verify
```

However, the CI workflow will still run these checks, so it's better to fix any issues rather than bypassing the hooks.
