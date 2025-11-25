---
name: Create Feature Branch
description: Creates a new git branch for a feature when starting a new spec
version: 1
triggers:
  - type: session-new
actions:
  - type: agent-message
    message: |
      Before implementing any spec tasks, check if you're on a dedicated feature branch:
      1. Run `git branch --show-current` to check current branch
      2. If on `main` or `dev`, create a feature branch: `git checkout -b feature/{spec-name}`
      3. The branch name should match the spec folder name (e.g., feature/air-quality-dialog)
      4. Confirm the branch was created before proceeding with implementation
---

# Create Feature Branch

This hook ensures a feature branch is created when starting work on a new spec.
