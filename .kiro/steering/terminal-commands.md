---
inclusion: always
---

# Terminal Command Execution Guidelines

## Shell Environment

**This workspace uses Git Bash on Windows.** Use Unix-style commands (ls, cat, rm, cp, mkdir) rather than PowerShell or CMD equivalents.

## Command Selection

Use `executePwsh` for quick commands that should complete:
- `git status`, `git diff`, `git add`, `git commit`
- `ruff check`, `ruff format`, `pyright`
- `pytest` (with reasonable timeout)
- File operations, package installs

Use `controlPwshProcess` ONLY for long-running/background processes:
- `briefcase dev`, `npm run dev`, `yarn start`
- Build watchers, dev servers
- Any command that runs indefinitely

## Git Bash Tips

1. Use Unix-style commands: `ls`, `cat`, `rm`, `cp`, `mkdir -p`
2. Use forward slashes in paths: `src/accessiweather/app.py`
3. Home directory: `~` or `$HOME`
4. Command chaining: `&&` (run if previous succeeds) or `;` (run regardless)
5. Set reasonable timeouts (30-60s for most commands, longer for tests)
6. Prefer `--tb=short` or `--tb=line` for pytest to reduce output

## Timeout Handling

If `executePwsh` times out but the command likely succeeded (e.g., git commit), proceed with the workflow rather than retrying indefinitely.
