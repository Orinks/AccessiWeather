# CI/CD Pipeline Setup Guide

This guide explains how to set up and use the CI/CD pipeline for AccessiWeather.

## Overview

The AccessiWeather CI/CD pipeline consists of three main workflows:

1. **Continuous Integration (ci.yml)** - Code quality, testing, and security checks
2. **Build and Package (build.yml)** - Application building and packaging
3. **Release (release.yml)** - Automated release creation and deployment

## Workflow Triggers

### Continuous Integration
- **Push** to `main` or `dev` branches
- **Pull requests** targeting `main` or `dev` branches
- **Manual dispatch** via GitHub Actions UI

### Build and Package
- **Push** to `main` or `dev` branches (after CI passes)
- **Manual dispatch** with optional version override
- **Workflow completion** from CI workflow

### Release
- **Push** to `main` branch (excluding documentation changes)
- **Manual dispatch** with version and pre-release options

## Pipeline Stages

### 1. Quality Gate (CI Workflow)

#### Test Suite
- Runs on Python 3.11 and 3.12
- Executes unit tests with pytest
- Generates coverage reports
- Uploads coverage to Codecov

#### Code Quality
- Black code formatting check
- isort import sorting check
- flake8 linting
- mypy type checking

#### Security Scan
- Bandit security linting
- Safety dependency vulnerability check
- Generates security reports

#### Integration Tests
- GUI and service integration tests
- Application startup verification

### 2. Build Stage (Build Workflow)

#### Version Management
- Extracts version from pyproject.toml
- Updates setup.py and version.py
- Supports manual version override

#### Application Build
- PyInstaller executable creation
- Windows-specific optimizations
- Hidden import configurations

#### Packaging
- Portable ZIP archive creation
- Build artifact validation
- Artifact upload with retention

#### Installer Creation
- Inno Setup installer build
- Version synchronization
- Installer validation

### 3. Release Stage (Release Workflow)

#### Version Validation
- Checks for existing releases
- Prevents duplicate releases
- Validates version format

#### Release Artifacts
- Builds final release versions
- Generates SHA256 checksums
- Creates comprehensive release notes

#### GitHub Release
- Creates tagged release
- Uploads installer and portable versions
- Includes checksums and documentation

## Branch Strategy

### Development Workflow
```
feature/branch → dev → main
      ↓          ↓      ↓
   CI only   CI + Build  CI + Build + Release
```

### Branch Protection
- `main`: Requires PR review, CI passing
- `dev`: Requires CI passing
- Feature branches: CI validation on PR

## Artifact Management

### Build Artifacts
- **Location**: GitHub Actions artifacts
- **Retention**: 30 days (dev), 90 days (installers), 365 days (releases)
- **Naming**: `{AppName}_{Type}_v{Version}.{ext}`

### Release Assets
- Windows Installer: `AccessiWeather_Setup_v{version}.exe`
- Portable Archive: `AccessiWeather_Portable_v{version}.zip`
- Checksums: `checksums.txt`

## Configuration Files

### Required Files
- `.github/workflows/ci.yml` - CI workflow
- `.github/workflows/build.yml` - Build workflow
- `.github/workflows/release.yml` - Release workflow
- `pyproject.toml` - Version source and dependencies
- `AccessiWeather.spec` - PyInstaller configuration
- `installer/AccessiWeather.iss` - Inno Setup script

### Environment Variables
- `GITHUB_TOKEN` - Automatically provided by GitHub
- Additional secrets can be added in repository settings

## Usage Instructions

### Running CI Manually
1. Go to Actions tab in GitHub repository
2. Select "Continuous Integration" workflow
3. Click "Run workflow"
4. Choose branch and click "Run workflow"

### Creating a Build
1. Push to `dev` or `main` branch (CI will trigger build automatically)
2. Or manually dispatch "Build and Package" workflow
3. Optionally override version in manual dispatch

### Creating a Release
1. **Automatic**: Push to `main` branch with updated version in pyproject.toml
2. **Manual**: Dispatch "Release" workflow with version parameter

### Version Management
- Update version in `pyproject.toml`
- CI/CD will automatically sync to `setup.py` and `version.py`
- Use semantic versioning (e.g., 1.0.0, 1.0.1, 1.1.0)

## Monitoring and Troubleshooting

### Viewing Workflow Status
- GitHub repository → Actions tab
- Click on specific workflow run for details
- View logs for each job and step

### Common Issues

#### CI Failures
- **Test failures**: Check test logs, fix failing tests
- **Linting errors**: Run pre-commit hooks locally
- **Security issues**: Review bandit/safety reports

#### Build Failures
- **PyInstaller errors**: Check hidden imports and exclusions
- **Version conflicts**: Verify version format and uniqueness
- **Dependency issues**: Update requirements files

#### Release Failures
- **Duplicate version**: Update version in pyproject.toml
- **Missing artifacts**: Check build workflow completion
- **Permission errors**: Verify GITHUB_TOKEN permissions

### Local Testing

#### Pre-commit Hooks
```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

#### Local Build Testing
```bash
pip install PyInstaller
python -m PyInstaller AccessiWeather.spec
```

#### Act CLI (Local GitHub Actions)
```bash
# Install act CLI
choco install act-cli

# Run CI workflow locally
act -W .github/workflows/ci.yml
```

## Security Considerations

### Secrets Management
- Use GitHub Secrets for sensitive data
- Never commit API keys or passwords
- Rotate secrets regularly

### Dependency Security
- Automated vulnerability scanning with Safety
- Regular dependency updates
- Security advisory monitoring

### Code Signing
- Future enhancement for Windows code signing
- Requires code signing certificate
- Improves user trust and security

## Performance Optimization

### Caching Strategy
- pip dependencies cached between runs
- Build artifacts cached for reuse
- Cache keys based on dependency files

### Parallel Execution
- Test matrix runs in parallel
- Independent jobs run concurrently
- Optimized for fast feedback

### Resource Management
- Windows runners for native builds
- Appropriate timeout settings
- Efficient artifact storage

## Maintenance

### Regular Tasks
- Update workflow dependencies monthly
- Review and update security tools
- Monitor build performance metrics
- Update documentation as needed

### Workflow Updates
- Test changes in feature branches
- Use act CLI for local validation
- Monitor for breaking changes in actions

### Dependency Management
- Keep GitHub Actions up to date
- Update Python versions as needed
- Review and update tool versions
