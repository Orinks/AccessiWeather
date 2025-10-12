# Version Management Implementation - 0.4 Release Preparation

## Objective
Make `pyproject.toml` the single source of truth for version numbers. When changing the version in `pyproject.toml`, that change should automatically propagate everywhere without needing to update multiple files.

## Changes Implemented

### 1. pyproject.toml
- **Removed** duplicate `version` field from `[tool.briefcase]` section
- **Updated** version from `0.9.4.dev0` to `0.4.0` for release
- **Result**: `[project] version` is now the ONLY place to define version

### 2. src/accessiweather/__init__.py
- **Updated** `_read_pyproject_version()` function to read ONLY from `[project]` section
- **Removed** fallback to `[tool.briefcase]` version (which no longer exists)
- **Added** documentation clarifying single source of truth approach

### 3. tests/test_version_management.py (NEW)
Created comprehensive test suite with 5 tests:
- Verifies `[project]` version exists and is valid
- Ensures `[tool.briefcase]` does NOT have duplicate version field
- Tests version reading logic in `__init__.py`
- Tests version reading via `installer/make.py`
- Validates PEP 440 version format compliance

## Verification Results

✅ **All version management tests pass** (5/5)
✅ **Ruff lint checks pass** - No errors in modified files
✅ **Ruff format checks pass** - All files properly formatted
✅ **Version propagation verified** - Single change updates everywhere
✅ **installer/make.py** correctly reads version from `[project]`
✅ **src/accessiweather/__init__.py** correctly reads version from `[project]`

## How to Change Version (Single Source of Truth)

Edit `pyproject.toml` **[project]** section:

```toml
[project]
name = "accessiweather"
version = "X.Y.Z"  ← CHANGE THIS LINE ONLY
description = "..."
```

That's it! The version will automatically propagate to:
- Package metadata (via `importlib.metadata`)
- Installer builds (via `installer/make.py`)
- Application code (via `__init__.py`)
- Briefcase builds (reads from `[project]` automatically)

## Current State

**Version**: 0.4.0
**Branch**: copilot/prepare-04-release
**Status**: Ready for 0.4 release

## Technical Details

### Version Reading Flow

1. **When installed as package**: `importlib.metadata.version("accessiweather")`
2. **When running from source**: `_read_pyproject_version()` reads `[project] version`
3. **Build scripts**: `installer/make.py` reads `[project] version` via `tomllib`

### Why This Approach?

- **DRY Principle**: Don't Repeat Yourself - version defined once
- **PEP 621**: Follows modern Python packaging standards
- **Briefcase Compatible**: Briefcase 0.3.23+ automatically uses `[project]` version
- **Error Prevention**: Eliminates version mismatch bugs
- **Maintainability**: Simple to update, less prone to mistakes

### File Changes Summary

```
Modified:
  - pyproject.toml (removed duplicate, updated to 0.4.0)
  - src/accessiweather/__init__.py (simplified version reading)
  
Added:
  - tests/test_version_management.py (new test suite)
```

## Testing

To verify version management:

```bash
# Run version management tests
python3 -m pytest tests/test_version_management.py -v

# Or manually run tests
cd tests && python3 -c "
from test_version_management import TestVersionManagement
test = TestVersionManagement()
for name in dir(test):
    if name.startswith('test_'):
        getattr(test, name)()
print('All tests passed!')
"
```

## Notes

- This implementation follows PEP 621 (Storing project metadata in pyproject.toml)
- Compatible with Briefcase 0.3.23+
- No changes needed to CI/CD workflows - they read from pyproject.toml correctly
- Version format validated against PEP 440

## Commit History

1. Initial plan (2d39281)
2. Make pyproject.toml single source of truth for version (75855fa)
3. Update version to 0.4.0 for release (c083830)
