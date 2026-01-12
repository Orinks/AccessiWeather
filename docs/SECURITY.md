# Security Documentation

## Overview

AccessiWeather implements multiple layers of security controls to protect users from command injection, path traversal, and other file-based vulnerabilities. This document explains the security architecture, particularly around subprocess execution and file path handling.

## Critical Security Fixes

### Command Injection Vulnerability (CWE-78)

**Issue:** The update service previously used `subprocess.Popen()` with `shell=True` when executing batch scripts and MSI installers. This created a command injection vulnerability where an attacker who could influence file paths could execute arbitrary commands.

**Impact:** An attacker who could modify the update cache directory or influence downloaded files could execute arbitrary commands with user privileges.

**Resolution:** All subprocess calls now:
1. Use `shell=False` (the default) - never use `shell=True`
2. Pass arguments as a list, not a string
3. Validate all file paths before execution
4. Use absolute paths resolved from validated relative paths

### Path Traversal Vulnerability (CWE-22)

**Issue:** File paths were not validated before use, allowing potential path traversal attacks (e.g., `../../system32/malicious.exe`).

**Impact:** An attacker could potentially escape the application directory and access or modify files outside the intended scope.

**Resolution:** All file paths are now validated using the `path_validator` module to:
1. Check for `..` sequences in paths
2. Verify files are within expected parent directories
3. Resolve paths to absolute form
4. Check for suspicious characters

## Security Architecture

### Defense-in-Depth Strategy

AccessiWeather implements multiple layers of security controls:

```
┌─────────────────────────────────────────────┐
│ Layer 1: Input Validation                  │
│  - File extension validation (.msi, .zip)  │
│  - File existence checks                   │
│  - Suspicious character detection          │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│ Layer 2: Path Security                     │
│  - Path traversal detection                │
│  - Absolute path resolution                │
│  - Directory containment validation        │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│ Layer 3: Subprocess Execution               │
│  - NO shell=True                           │
│  - List-based arguments (not strings)      │
│  - Validated absolute paths only           │
└─────────────────────────────────────────────┘
```

### Path Validation Module

The `src/accessiweather/utils/path_validator.py` module provides security-focused validation functions:

#### Core Validation Functions

| Function | Purpose | Raises |
|----------|---------|--------|
| `validate_file_extension()` | Verify file has expected extension | `ValueError` |
| `validate_file_exists()` | Verify file exists | `FileNotFoundError` |
| `validate_no_path_traversal()` | Detect `..` sequences | `SecurityError` |
| `validate_path_within_directory()` | Ensure path is within parent dir | `SecurityError` |
| `validate_no_suspicious_characters()` | Check for shell metacharacters | `SecurityError` |
| `validate_executable_path()` | Comprehensive validation (all above) | Multiple |

#### Usage Example

```python
from pathlib import Path
from accessiweather.utils.path_validator import validate_executable_path

# Validate an MSI installer before execution
try:
    msi_path = validate_executable_path(
        downloaded_file,
        expected_suffix=".msi",
        expected_parent=cache_dir
    )
    # Safe to use validated path with subprocess
    subprocess.Popen(["msiexec", "/i", str(msi_path), "/norestart"])
except (FileNotFoundError, ValueError, SecurityError) as e:
    logger.error(f"Path validation failed: {e}")
    # Handle error appropriately
```

## Secure Subprocess Usage

### ✅ Correct Pattern

```python
import subprocess
from pathlib import Path
from accessiweather.utils.path_validator import validate_executable_path

# 1. Validate the path
validated_path = validate_executable_path(
    user_provided_path,
    expected_suffix=".msi",
    expected_parent=allowed_directory
)

# 2. Execute with list arguments, NO shell=True
subprocess.Popen([
    "msiexec",
    "/i",
    str(validated_path),  # Use validated absolute path
    "/norestart"
])
```

### ❌ Dangerous Patterns (DO NOT USE)

```python
# WRONG: Using shell=True opens command injection
subprocess.Popen(f"msiexec /i {path}", shell=True)  # NEVER DO THIS!

# WRONG: String argument without validation
subprocess.Popen(path, shell=True)  # NEVER DO THIS!

# WRONG: Unvalidated paths
subprocess.Popen(["msiexec", "/i", user_input])  # Validate first!

# WRONG: Relative paths without validation
subprocess.Popen(["cmd", "/c", "script.bat"])  # Use absolute paths!
```

## Module-Specific Security Controls

### github_update_service.py

**Function:** `schedule_portable_update_and_restart()`

**Security Controls:**
1. **Platform Check:** Windows-only, fails fast on other platforms
2. **Path Validation:**
   - Validates `zip_path` exists and has `.zip` extension
   - Validates `batch_path` is within `target_dir`
   - Validates `target_dir` is writable
3. **Subprocess Execution:**
   - NO `shell=True` parameter
   - Batch path passed as list argument: `[str(batch_path)]`
   - Detached process creation flags
4. **Batch Script Security:**
   - All variables quoted (e.g., `"%ZIP_PATH%"`)
   - Uses PowerShell for safe ZIP extraction
   - Explicit cleanup of temporary files

**Documentation:** See comprehensive docstring (lines 290-339) and inline comments throughout the function.

### update_handlers.py

#### Function: `_run_msi_installer()`

**Security Controls:**
1. **Path Validation:**
   - Validates `msi_path` exists and has `.msi` extension
   - Resolves to absolute path
   - Checks for path traversal and suspicious characters
2. **Subprocess Execution:**
   - NO `shell=True` parameter
   - Arguments passed as list: `["msiexec", "/i", msi_path_str, "/norestart"]`
   - Uses validated absolute path

**Documentation:** See comprehensive docstring (lines 243-280) and inline comments.

#### Function: `_extract_portable_update()`

**Security Controls:**
1. **Path Validation:**
   - Validates `zip_path` exists and has `.zip` extension
   - Resolves to absolute path
   - Checks for path traversal and suspicious characters
2. **Delegation:**
   - Passes validated path to `schedule_portable_update_and_restart()`
   - Which applies additional validation and subprocess security

**Documentation:** See comprehensive docstring (lines 175-210) and inline comments.

## Security Testing

### Unit Tests

Security controls are validated by comprehensive unit test suites:

| Test File | Coverage |
|-----------|----------|
| `tests/test_path_validator.py` | Path validation utilities (716 lines) |
| `tests/test_github_update_service.py` | Subprocess security in update service |
| `tests/test_update_handlers.py` | Handler security (23 tests) |

### Test Coverage Areas

1. **Path Validation:**
   - Extension validation (case-insensitive)
   - File existence checks
   - Path traversal detection (`..` sequences)
   - Symlink escape prevention
   - Suspicious character detection
   - Directory containment validation

2. **Subprocess Security:**
   - Verify `shell=True` is NEVER used
   - Verify arguments passed as lists
   - Verify validated paths used
   - Verify proper exception handling

3. **Edge Cases:**
   - Relative paths
   - Absolute paths
   - Symlinks
   - Unicode filenames
   - Long paths
   - Property-based testing with Hypothesis

### Running Security Tests

```bash
# Run all tests
pytest -n auto -v

# Run path validation tests
pytest tests/test_path_validator.py -v

# Run update service security tests
pytest tests/test_github_update_service.py::TestSchedulePortableUpdateAndRestartSecurity -v

# Run update handler security tests
pytest tests/test_update_handlers.py::TestRunMsiInstallerSecurity -v
pytest tests/test_update_handlers.py::TestExtractPortableUpdateSecurity -v
```

## Security Best Practices

### For Developers

When adding new subprocess calls or file operations:

1. **NEVER use `shell=True`** unless absolutely necessary and fully documented
2. **ALWAYS validate paths** using `validate_executable_path()` or individual validation functions
3. **ALWAYS use list arguments** for subprocess, never strings
4. **ALWAYS use absolute paths** after validation
5. **ALWAYS handle validation exceptions** (FileNotFoundError, ValueError, SecurityError)
6. **ALWAYS add unit tests** verifying security controls
7. **ALWAYS add security comments** explaining why controls are needed

### Code Review Checklist

When reviewing code with subprocess calls:

- [ ] No `shell=True` parameter (or explicitly documented why it's required)
- [ ] Arguments passed as list, not string
- [ ] All file paths validated before use
- [ ] Paths resolved to absolute form
- [ ] Validation exceptions handled appropriately
- [ ] Unit tests cover security scenarios
- [ ] Documentation explains security considerations

### Common Pitfalls

1. **Platform Differences:**
   - Windows handles `shell=True` differently than Unix
   - Always test on target platforms
   - Use platform-specific code paths when necessary

2. **Argument Injection:**
   - Even without `shell=True`, unvalidated arguments can be dangerous
   - Always validate file extensions and paths
   - Quote variables in shell scripts

3. **Race Conditions:**
   - Validate paths just before use
   - Use atomic operations when possible
   - Be aware of TOCTOU (Time-of-check to time-of-use) issues

## Vulnerability Disclosure

If you discover a security vulnerability in AccessiWeather:

1. **DO NOT** open a public GitHub issue
2. **DO** email the maintainers privately (see README.md for contact info)
3. Provide detailed description of the vulnerability
4. Include steps to reproduce if possible
5. Allow reasonable time for a fix before public disclosure

## References

### CWE (Common Weakness Enumeration)

- **CWE-78:** Improper Neutralization of Special Elements used in an OS Command ('OS Command Injection')
  - https://cwe.mitre.org/data/definitions/78.html
- **CWE-22:** Improper Limitation of a Pathname to a Restricted Directory ('Path Traversal')
  - https://cwe.mitre.org/data/definitions/22.html

### OWASP Resources

- **OWASP Top 10 - A03:2021 Injection**
  - https://owasp.org/Top10/A03_2021-Injection/
- **OWASP Cheat Sheet - OS Command Injection Defense**
  - https://cheatsheetseries.owasp.org/cheatsheets/OS_Command_Injection_Defense_Cheat_Sheet.html

### Python Security Resources

- **Python subprocess module documentation**
  - https://docs.python.org/3/library/subprocess.html#security-considerations
- **PEP 551 - Security transparency in the Python runtime**
  - https://www.python.org/dev/peps/pep-0551/

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-01-11 | Initial security documentation following fix of CWE-78 and CWE-22 vulnerabilities |

---

**Last Updated:** 2026-01-11
**Maintained By:** AccessiWeather Development Team
