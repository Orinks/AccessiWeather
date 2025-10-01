Droid-assisted: fix settings dialog alignment error

This PR replaces invalid Toga Pack alignment value 'baseline' with 'center' in settings_dialog.py rows, fixing:

Error: Failed to open settings: Invalid value 'baseline' for property alignment; Valid values are: bottom, center, left, right, top

Validation:
- Synced repo and created feature branch
- Installed deps in .venv and ran full test suite (all green)
- Ran ruff lint/format and pre-commit hooks (all passed)

Impact: Unblocks opening the Settings dialog on Toga 0.5.x (toga-winforms backend).
