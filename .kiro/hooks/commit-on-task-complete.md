---
name: Commit on Task Complete
description: Commits and pushes changes when a full task (including all subtasks) is completed
version: 1
triggers:
  - type: agent-complete
actions:
  - type: agent-message
    message: |
      If you just completed a full task from a spec (parent task with all subtasks marked done):
      1. Run `git status` to see changed files
      2. Stage relevant files with `git add {files}`
      3. Create a conventional commit:
         ```
         feat({scope}): {short description}

         - {bullet point of what was done}
         - {another bullet point}

         Completes task {N} of {spec-name} spec
         ```
      4. Push to the feature branch: `git push origin {branch-name}`
      5. Inform the user that changes have been committed and pushed

      Skip this if no task was completed or if changes were already committed.
---

# Commit on Task Complete

This hook ensures changes are committed and pushed after completing a full spec task.
