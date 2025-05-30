# Build and Artifact Management

This document describes the streamlined build and artifact management system implemented for AccessiWeather.

## Overview

The build system provides automated, reproducible builds with essential artifact management, basic validation, and checksums. It's designed to be simple, reliable, and efficient for a small open-source project.

## Build Workflow Architecture

### Workflow Triggers
- **Push to main/dev**: Automatic builds after successful CI
- **Manual dispatch**: On-demand builds with optional version override
- **CI completion**: Triggered after successful CI pipeline completion

### Build Jobs

#### 1. Build Job (`build`)
**Purpose**: Create the main application executable and portable package

**Key Features**:
- ✅ **Smart caching** for pip dependencies and PyInstaller builds
- ✅ **Version management** with dynamic injection into source files
- ✅ **SHA256 checksums** for integrity verification
- ✅ **Build performance optimization** with configurable cache skipping

**Outputs**:
- Windows executable (`AccessiWeather.exe`)
- Portable ZIP package (`AccessiWeather_Portable_v{version}.zip`)
- Checksums file (`checksums.txt`)

#### 2. Installer Job (`installer`)
**Purpose**: Create Windows installer using Inno Setup

**Key Features**:
- ✅ **Automatic Inno Setup installation** and configuration
- ✅ **Dynamic version injection** into installer script
- ✅ **Installer checksum generation** and validation
- ✅ **Environment variable configuration** for build paths

**Outputs**:
- Windows installer (`AccessiWeather_Setup_v{version}.exe`)
- Updated checksums with installer hash

#### 3. Validation Job (`validate`)
**Purpose**: Comprehensive artifact validation and quality assurance

**Key Features**:
- ✅ **File presence validation** for all required artifacts
- ✅ **Checksum verification** using SHA256 hashes
- ✅ **Build metadata validation** with JSON schema checking
- ✅ **Size analysis** and reporting
- ✅ **Validation report generation** for audit trails

**Outputs**:
- Validation report (`validation-report.json`)
- Comprehensive build status summary

## Build Metadata System

### Version Management
The build system implements dynamic version management:

```python
# Generated in src/accessiweather/version.py
__version__ = "0.9.3"
__build_hash__ = "a1b2c3d"
__build_date__ = "2024-01-15T10:30:00Z"
__branch__ = "dev"

def get_version_info():
    """Get comprehensive version information."""
    return {
        "version": __version__,
        "build_hash": __build_hash__,
        "build_date": __build_date__,
        "branch": __branch__
    }
```

### Build Metadata JSON
Each build generates comprehensive metadata:

```json
{
  "version": "0.9.3",
  "commit_hash": "a1b2c3d",
  "build_date": "2024-01-15T10:30:00Z",
  "branch": "dev",
  "artifacts": {
    "executable": {
      "path": "AccessiWeather/AccessiWeather.exe",
      "size_bytes": 45678901,
      "sha256": "abc123..."
    },
    "portable_zip": {
      "path": "AccessiWeather_Portable_v0.9.3.zip",
      "size_bytes": 23456789,
      "sha256": "def456..."
    }
  },
  "build_environment": {
    "os": "windows-latest",
    "python_version": "3.12",
    "runner": "GitHub Actions"
  }
}
```

## Artifact Management

### Artifact Types
| Artifact | Purpose | Retention | Compression |
|----------|---------|-----------|-------------|
| **Build Artifacts** | Development builds | 30 days | Level 6 |
| **Installer Artifacts** | Release candidates | 90 days | Level 6 |
| **Validation Reports** | Audit trails | 365 days | Default |

### Checksums and Integrity
All artifacts include SHA256 checksums for integrity verification:

```
# AccessiWeather v0.9.3 Build Checksums
# Generated on: 2024-01-15T10:30:00Z
# Commit: a1b2c3d
# Branch: dev

abc123...  AccessiWeather/AccessiWeather.exe
def456...  AccessiWeather_Portable_v0.9.3.zip
ghi789...  AccessiWeather_Setup_v0.9.3.exe
```

## Caching Strategy

### PyInstaller Build Cache
- **Cache Key**: Based on source code and spec file hashes
- **Cache Path**: `~/.cache/pyinstaller`, `build/`, `*.toc`
- **Benefits**: 50-80% faster subsequent builds
- **Invalidation**: Automatic on source code changes

### Dependency Cache
- **Cache Key**: Based on requirements files and pyproject.toml
- **Cache Path**: `~\AppData\Local\pip\Cache`
- **Benefits**: Faster dependency installation
- **Retention**: Persistent across builds

### Cache Control
```yaml
# Skip cache for clean builds
workflow_dispatch:
  inputs:
    skip_cache:
      description: 'Skip build cache'
      type: boolean
      default: false
```

## Build Validation

### Validation Checks
1. **File Presence**: All required artifacts exist
2. **Checksum Verification**: SHA256 hash validation
3. **Metadata Validation**: JSON schema and content verification
4. **Size Analysis**: Artifact size reporting and validation
5. **Version Consistency**: Version matching across all components

### Validation Report
```json
{
  "validation_date": "2024-01-15T10:35:00Z",
  "version": "0.9.3",
  "build_hash": "a1b2c3d",
  "total_size_mb": 67.8,
  "artifacts_validated": 4,
  "checksums_verified": true,
  "metadata_valid": true,
  "status": "PASSED"
}
```

## Security Features

### Integrity Protection
- ✅ **SHA256 checksums** for all artifacts
- ✅ **Build metadata** with commit traceability
- ✅ **Validation reports** for audit trails
- ✅ **Artifact retention** policies for compliance

### Build Reproducibility
- ✅ **Pinned dependencies** in requirements files
- ✅ **Consistent build environment** (Python 3.12, Windows)
- ✅ **Version-controlled build scripts** and configurations
- ✅ **Build metadata** for exact reproduction

## Performance Optimization

### Build Speed Improvements
- **Caching**: 50-80% faster builds with PyInstaller cache
- **Parallel Jobs**: Independent installer and validation jobs
- **Optimized Dependencies**: Minimal dependency installation
- **Compression**: Efficient artifact compression (level 6)

### Resource Usage
- **Memory**: Optimized PyInstaller settings
- **Storage**: Intelligent artifact retention policies
- **Network**: Cached dependencies reduce download time

## Usage Guide

### Manual Build Trigger
```bash
# Trigger build with version override
gh workflow run "Build and Package" \
  --field version_override="1.0.0" \
  --field skip_cache=false
```

### Local Build Testing
```bash
# Test build locally (requires PyInstaller)
python -m PyInstaller --clean --noconfirm AccessiWeather.spec

# Verify checksums
Get-FileHash dist/AccessiWeather/AccessiWeather.exe -Algorithm SHA256
```

### Artifact Download
```bash
# Download latest build artifacts
gh run download --name "windows-installer-0.9.3"
```

## Troubleshooting

### Common Issues

1. **Build Cache Issues**
   - Solution: Use `skip_cache: true` in manual dispatch
   - Check: PyInstaller cache corruption

2. **Checksum Mismatches**
   - Solution: Rebuild from clean state
   - Check: File corruption during transfer

3. **Validation Failures**
   - Solution: Review validation report details
   - Check: Missing dependencies or build errors

4. **Large Artifact Sizes**
   - Solution: Review PyInstaller excludes
   - Check: Unnecessary dependencies included

### Getting Help
- Check build logs in GitHub Actions
- Review validation reports for detailed analysis
- Examine build metadata for environment details
- Compare checksums for integrity verification

## Future Enhancements

### Planned Features
- **Multi-platform builds** (Linux, macOS)
- **Automated performance benchmarking**
- **Build artifact scanning** for additional security
- **Release automation** integration
- **Build metrics** and analytics dashboard

### Configuration Options
- **Custom retention policies** per artifact type
- **Configurable compression levels**
- **Build notification** integrations
- **Custom validation rules** and thresholds
