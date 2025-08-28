# Quality Gates and Security Checks

This document describes the comprehensive quality gates and security checks implemented in the AccessiWeather CI/CD pipeline.

## Overview

The CI/CD pipeline enforces strict quality standards through automated checks that must pass before code can be merged or deployed. These checks ensure code quality, security, and maintainability.

## Quality Thresholds

The following thresholds are configurable via environment variables in the GitHub Actions workflow:

| Metric | Threshold | Environment Variable | Description |
|--------|-----------|---------------------|-------------|
| Code Complexity | 10 | `MAX_COMPLEXITY` | Maximum cyclomatic complexity per function |
| Security Severity | medium+ | `SECURITY_SEVERITY_THRESHOLD` | Minimum security issue severity that fails builds |

## Pipeline Jobs

### 1. Test Suite (`test`)
- **Purpose**: Run unit tests with coverage analysis
- **Tools**: pytest, pytest-cov
- **Quality Gates**:
  - ✅ All tests must pass
- **Artifacts**: Coverage reports (XML, HTML)
- **Matrix**: Python 3.11, 3.12

### 2. Code Quality (`code-quality`)
- **Purpose**: Static code analysis and style checking
- **Tools**:
  - Pre-commit hooks (black, isort, flake8, mypy)
  - Radon (complexity analysis)
  - Xenon (complexity enforcement)
- **Quality Gates**:
  - ✅ Code formatting must be consistent (black)
  - ✅ Import sorting must be correct (isort)
  - ✅ Linting rules must pass (flake8)
  - ✅ Type hints must be valid (mypy)
  - ✅ Complexity must not exceed threshold
- **Artifacts**: Complexity and maintainability reports

### 3. Security Scan (`security`)
- **Purpose**: Identify security vulnerabilities
- **Tools**:
  - Bandit (static security analysis)
  - Safety (dependency vulnerabilities)
  - pip-audit (additional dependency scanning)
  - Semgrep (advanced pattern detection)
- **Quality Gates**:
  - ✅ No medium+ severity security issues
  - ✅ No known vulnerable dependencies
- **Artifacts**: Security scan reports (JSON format)

### 4. Integration Tests (`integration`)
- **Purpose**: Test component interactions
- **Dependencies**: test, code-quality
- **Quality Gates**:
  - ✅ All integration tests must pass
  - ✅ Application startup must succeed

### 5. Smoke Tests (`smoke`)
- **Purpose**: Basic functionality verification
- **Dependencies**: test
- **Quality Gates**:
  - ✅ Critical user flows must work

### 6. Quality Gate (`quality-gate`)
- **Purpose**: Final validation of all quality checks
- **Dependencies**: All previous jobs
- **Behavior**:
  - ✅ Fails if any dependent job fails
  - ✅ Generates comprehensive quality summary
- **Artifacts**: Quality gate summary report

## Security Tools Configuration

### Bandit
- **Configuration**: `.bandit`
- **Scope**: Python source code security analysis
- **Exclusions**: Test files, generated API clients
- **Severity**: Medium and High confidence issues

### Safety & pip-audit
- **Purpose**: Dependency vulnerability scanning
- **Behavior**: Fails on any known vulnerabilities
- **Reports**: JSON format for detailed analysis

### Semgrep
- **Configuration**: Auto (community rules)
- **Scope**: Advanced security pattern detection
- **Behavior**: Fails on security rule violations

## Code Quality Tools Configuration

### Pre-commit Hooks
- **Configuration**: `.pre-commit-config.yaml`
- **Tools**: ruff (linting & formatting), mypy, basic checks
- **Integration**: Runs in CI to ensure consistency

### Ruff
- **Configuration**: `pyproject.toml`
- **Max Line Length**: 100 characters
- **Max Complexity**: 15 (enforced)
- **Exclusions**: Generated code, build artifacts
- **Features**: Combines linting, formatting, and import sorting

### Complexity Analysis
- **Tools**: Radon (analysis), Xenon (enforcement)
- **Metrics**: Cyclomatic complexity, maintainability index
- **Threshold**: Functions with complexity > 10 fail the build

## Artifact Generation

The pipeline generates the following artifacts for analysis:

| Artifact | Job | Content |
|----------|-----|---------|
| `coverage-report-*` | test | HTML coverage reports |
| `code-quality-reports` | code-quality | Complexity and maintainability metrics |
| `security-reports` | security | Security scan results from all tools |
| `quality-gate-summary` | quality-gate | Overall pipeline status summary |

## Local Development

### Running Quality Checks Locally

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run pre-commit hooks
pre-commit install
pre-commit run --all-files

# Run ruff checks manually
ruff check src/accessiweather tests/
ruff format src/accessiweather tests/

# Run tests with coverage
pytest --cov=src/accessiweather

# Run security scans
bandit -r src/accessiweather
safety check
pip-audit

# Check complexity
radon cc src/accessiweather --min C
xenon --max-absolute 10 src/accessiweather
```

### Bypassing Quality Gates (Emergency Only)

In exceptional circumstances, quality gates can be bypassed:

1. **Complexity**: Refactor code or add `# noqa: C901` for specific functions
2. **Security**: Add exclusions to `.bandit` or use `# nosec` comments
3. **Style**: Run `pre-commit run --all-files` to auto-fix issues

⚠️ **Warning**: Bypassing quality gates should be rare and require code review approval.

## Troubleshooting

### Common Issues

1. **Low Test Coverage (Informational)**
   - Add more unit tests for critical paths
   - Remove unused code
   - Check for untested error paths

2. **High Complexity**
   - Break large functions into smaller ones
   - Extract helper methods
   - Simplify conditional logic

3. **Security Issues**
   - Review flagged code patterns
   - Update vulnerable dependencies
   - Add security exclusions if false positive

4. **Style Issues**
   - Run `black src/ tests/`
   - Run `isort src/ tests/`
   - Fix flake8 warnings manually

### Getting Help

- Check artifact reports for detailed analysis
- Review job logs for specific error messages
- Consult tool documentation for configuration options
- Ask for code review help if quality gates are consistently failing
