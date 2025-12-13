---
inclusion: always
---

# Git & GitHub Guidelines

## Shell Environment

**This workspace uses Git Bash on Windows.** Standard git commands work as expected.

## Git Commands

**Branch Management:**
```bash
git branch                    # List branches
git checkout -b feature-name  # Create and switch to new branch
git switch main               # Switch to existing branch
git branch -d feature-name    # Delete merged branch
```

**Common Operations:**
```bash
git status                    # Check working tree status
git add .                     # Stage all changes
git commit -m "message"       # Commit with message
git pull origin main          # Pull latest from remote
git push origin branch-name   # Push branch to remote
git log --oneline -10         # View recent commits
git diff                      # View unstaged changes
git diff --staged             # View staged changes
```

**Stashing:**
```bash
git stash                     # Stash current changes
git stash pop                 # Apply and remove latest stash
git stash list                # List all stashes
```

## GitHub CLI (gh)

**Authentication:**
```bash
gh auth status                # Check auth status
gh auth login                 # Login to GitHub
```

**Pull Requests:**
```bash
gh pr create --title "Title" --body "Description"
gh pr list                    # List PRs
gh pr view 123                # View PR details
gh pr merge 123               # Merge PR
gh pr checkout 123            # Checkout PR locally
```

**Issues:**
```bash
gh issue create --title "Title" --body "Description"
gh issue list                 # List issues
gh issue view 123             # View issue details
gh issue close 123            # Close issue
```

**Releases:**
```bash
gh release create v1.0.0 --title "Release Title" --notes "Notes"
gh release list               # List releases
```

## GitHub API (gh api)

**Basic Pattern:**
```bash
gh api /repos/{owner}/{repo}/endpoint
gh api -X POST /repos/{owner}/{repo}/endpoint -f field=value
gh api -X PATCH /repos/{owner}/{repo}/endpoint -f field=value
```

**Common Endpoints:**
```bash
# Get repo info
gh api /repos/{owner}/{repo}

# Edit PR (gh pr edit is deprecated)
gh api -X PATCH /repos/{owner}/{repo}/pulls/{pr_number} \
  -f title="New Title" -f body="New Description"

# List workflows
gh api /repos/{owner}/{repo}/actions/workflows

# Trigger workflow
gh api -X POST /repos/{owner}/{repo}/actions/workflows/{id}/dispatches \
  -f ref=main
```

## Best Practices

- **Commit messages**: Use imperative mood ("Add feature" not "Added feature")
- **Branch naming**: Use descriptive names (`feature/add-login`, `fix/crash-on-startup`)
- **Pull requests**: Keep focused on single feature/fix; write clear descriptions
- **Never force push** to shared branches (main, dev)
- **Pull before push** to avoid conflicts
- **Review diffs** before committing to catch unintended changes
