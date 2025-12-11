# Deployment Guide - AccessiWeather

**Generated:** December 11, 2025  
**Target Audience:** Release managers and CI/CD maintainers

---

## Deployment Overview

AccessiWeather uses **Briefcase** for cross-platform packaging and **GitHub Actions** for automated builds and releases. This guide covers the complete deployment pipeline from code to user installation.

---

## Build System Architecture

### Briefcase Packaging

**What is Briefcase?**
- Part of the BeeWare suite
- Converts Python apps into platform-native packages
- Creates installers for Windows (MSI), macOS (DMG), and Linux (AppImage)

**Configuration:** `pyproject.toml` (see `[tool.briefcase]` section)

### Platform Targets

| Platform | Installer Format | Build Environment | Output Location |
|----------|------------------|-------------------|-----------------|
| **Windows** | MSI | Windows Server (GitHub Actions) | `build/accessiweather/windows/app/*.msi` |
| **macOS** | DMG (Universal) | macOS (GitHub Actions) | `build/accessiweather/macOS/app/*.dmg` |
| **Linux** | AppImage | Ubuntu (planned) | `build/accessiweather/linux/appimage/*.AppImage` |

---

## CI/CD Pipeline

### GitHub Actions Workflows

```
┌─────────────────────────────────────────────────────────┐
│                  GitHub Repository                       │
│                                                          │
│  Push/PR ──┐                                            │
│            │                                            │
│            ▼                                            │
│       ┌─────────┐                                       │
│       │ ci.yml  │  ← Lint + Unit Tests (all platforms) │
│       └─────────┘                                       │
│                                                          │
│  Tag Push ─────┬────────────┐                          │
│                │            │                          │
│                ▼            ▼                          │
│       ┌────────────────┐  ┌──────────────────────┐   │
│       │ briefcase-     │  │ briefcase-release.   │   │
│       │ build.yml      │  │ yml                  │   │
│       │                │  │                      │   │
│       │ • Windows MSI  │──▶│ • Create Release   │   │
│       │ • macOS DMG    │  │ • Upload Artifacts   │   │
│       └────────────────┘  └──────────────────────┘   │
│                                                          │
│  Schedule (Daily) ──┐                                   │
│                     │                                   │
│                     ▼                                   │
│              ┌──────────────────┐                      │
│              │ nightly-         │                      │
│              │ release.yml      │                      │
│              │                  │                      │
│              │ • Nightly builds │                      │
│              │ • Pre-releases   │                      │
│              └──────────────────┘                      │
│                                                          │
│  Manual/Schedule ──┐                                    │
│                    │                                    │
│                    ▼                                    │
│           ┌──────────────────┐                         │
│           │ integration-     │                         │
│           │ tests.yml        │                         │
│           │                  │                         │
│           │ • Real API tests │                         │
│           └──────────────────┘                         │
└─────────────────────────────────────────────────────────┘
```

---

## Workflow Details

### 1. ci.yml - Continuous Integration

**Trigger:** Every push, every PR  
**Purpose:** Code quality checks and unit tests  
**Platforms:** Ubuntu, Windows, macOS (matrix)

**Steps:**
1. Checkout code
2. Set up Python 3.10+
3. Install dependencies (`pip install -e ".[dev]"`)
4. Run Ruff linter (`ruff check .`)
5. Run Ruff formatter check (`ruff format --check .`)
6. Run unit tests (`pytest -v -p pytest_asyncio`)
7. Generate coverage report
8. Upload coverage to artifacts

**Duration:** ~5-10 minutes  
**Failure Action:** Block PR merge

**Key Configuration:**
```yaml
env:
  FORCE_COLOR: "0"  # Prevent encoding issues on Windows
  TOGA_BACKEND: "toga_dummy"  # Use dummy backend for tests
```

### 2. briefcase-build.yml - Platform Builds

**Trigger:** Manual dispatch, tag push  
**Purpose:** Create platform-specific installers  
**Platforms:** Windows (MSI), macOS (DMG)

**Build Matrix:**
```yaml
matrix:
  os: [windows-latest, macos-latest]
  python-version: ["3.12"]
```

**Steps:**
1. Checkout code
2. Extract version from `pyproject.toml`
3. Set up Python 3.12
4. Install Briefcase (`pip install briefcase`)
5. Create platform app (`briefcase create`)
6. Build app bundle (`briefcase build`)
7. Package installer (`briefcase package`)
8. Upload artifacts (MSI or DMG)

**Duration:** ~15-30 minutes per platform  
**Output:** GitHub Actions artifacts (MSI, DMG)

**Platform-Specific Notes:**

**Windows:**
- Requires Visual Studio Build Tools
- MSI installer with desktop shortcut
- Includes `pythonnet` for Windows-specific features

**macOS:**
- Universal binary (Intel + Apple Silicon)
- Signed and notarized (if certs available)
- DMG with drag-to-Applications

### 3. briefcase-release.yml - Release Automation

**Trigger:** Tag push (e.g., `v0.4.2`)  
**Purpose:** Create GitHub Release with installers  
**Dependencies:** Calls `briefcase-build.yml` as sub-workflow

**Steps:**
1. Trigger `briefcase-build.yml` (builds MSI + DMG)
2. Wait for build completion
3. Download build artifacts
4. Extract version from tag
5. Create GitHub Release
6. Upload installers to release (MSI, DMG)
7. Generate release notes from `CHANGELOG.md`

**Duration:** ~20-40 minutes (includes build time)  
**Output:** GitHub Release with downloadable installers

**Release Assets:**
- `AccessiWeather-0.4.2-windows.msi`
- `AccessiWeather-0.4.2-macos.dmg`
- Source code (auto-generated by GitHub)

### 4. nightly-release.yml - Nightly Builds

**Trigger:** Schedule (daily at 2 AM UTC)  
**Purpose:** Provide cutting-edge builds for testing  
**Version Format:** `0.4.2-nightly-20251211`

**Steps:**
1. Generate nightly version (`{version}-nightly-{date}`)
2. Update `pyproject.toml` with nightly version
3. Run `briefcase-build.yml` with nightly version
4. Create GitHub Pre-Release (marked as pre-release)
5. Upload nightly installers
6. Clean up old nightlies (keep last 7 days)

**Duration:** ~20-40 minutes  
**Output:** GitHub Pre-Release with nightly installers

**Retention Policy:** Automatically delete nightlies older than 7 days

### 5. integration-tests.yml - API Integration Tests

**Trigger:** Manual dispatch, schedule (optional)  
**Purpose:** Test real API integrations (NWS, Open-Meteo, Visual Crossing)

**Steps:**
1. Checkout code
2. Set up Python 3.10+
3. Install dependencies
4. Run integration tests (`pytest -m "integration" -v`)
5. Report results (pass/fail)

**Duration:** ~5-10 minutes  
**Note:** Requires internet connection, may have rate limits

---

## Manual Deployment Process

### Prerequisites

1. **Briefcase installed:** `pip install briefcase`
2. **Platform requirements met:**
   - Windows: Visual Studio Build Tools
   - macOS: Xcode Command Line Tools
   - Linux: `python3-dev`, `build-essential`

### Step-by-Step Build

#### 1. Create Platform-Specific App Structure

```bash
briefcase create
```

**What this does:**
- Creates `build/accessiweather/{platform}/app/` directory
- Generates platform-specific template
- Copies source code to build location
- Configures entry points

**Output:** Platform-specific app skeleton

#### 2. Build Application

```bash
briefcase build
```

**What this does:**
- Compiles Python code
- Bundles dependencies
- Creates platform-native binary
- Configures app metadata (icons, version, etc.)

**Output:**
- Windows: `.exe` with dependencies
- macOS: `.app` bundle
- Linux: Executable with dependencies

#### 3. Package Installer

```bash
briefcase package
```

**What this does:**
- Creates installer/package
- Platform-specific:
  - **Windows:** MSI installer with WiX toolset
  - **macOS:** DMG disk image
  - **Linux:** AppImage (self-contained)

**Output:**
- `build/accessiweather/windows/app/AccessiWeather-0.4.2.msi`
- `build/accessiweather/macOS/app/AccessiWeather-0.4.2.dmg`
- `build/accessiweather/linux/appimage/AccessiWeather-0.4.2-x86_64.AppImage`

#### 4. Test Installer

**Windows:**
```bash
# Run MSI installer
msiexec /i build\accessiweather\windows\app\AccessiWeather-0.4.2.msi

# Or double-click MSI in Windows Explorer
```

**macOS:**
```bash
# Mount DMG
open build/accessiweather/macOS/app/AccessiWeather-0.4.2.dmg

# Drag AccessiWeather.app to Applications folder
# Launch from Applications
```

**Linux:**
```bash
# Make AppImage executable
chmod +x AccessiWeather-0.4.2-x86_64.AppImage

# Run AppImage
./AccessiWeather-0.4.2-x86_64.AppImage
```

---

## Release Process

### Version Numbering

**Format:** `MAJOR.MINOR.PATCH` (Semantic Versioning)

- **MAJOR:** Breaking changes
- **MINOR:** New features (backward compatible)
- **PATCH:** Bug fixes

**Examples:**
- `0.4.2` - Current version
- `0.5.0` - Next minor release (new features)
- `1.0.0` - First stable release

### Creating a Release

#### 1. Update Version

Edit `pyproject.toml`:
```toml
[project]
version = "0.4.3"
```

#### 2. Update CHANGELOG.md

Move "Unreleased" section to new version:
```markdown
## [0.4.3] - 2025-12-11

### Added
- New sound pack installer feature

### Fixed
- Fixed alert notification spam issue
```

#### 3. Commit Changes

```bash
git add pyproject.toml CHANGELOG.md
git commit -m "chore: Release 0.4.3"
git push origin main
```

#### 4. Create and Push Tag

```bash
git tag v0.4.3
git push origin v0.4.3
```

#### 5. GitHub Actions Automation

- `briefcase-build.yml` triggers automatically
- Builds MSI (Windows) and DMG (macOS)
- `briefcase-release.yml` triggers after build
- Creates GitHub Release
- Uploads installers to release

#### 6. Verify Release

- Check GitHub Releases page
- Download and test installers
- Verify release notes

#### 7. Update Website (Optional)

```bash
# Trigger update-pages.yml (automatic on push to main)
# Or manually update accessiweather.orinks.net
```

---

## Deployment Configuration

### pyproject.toml - Briefcase Configuration

**Key Sections:**

```toml
[tool.briefcase]
project_name = "AccessiWeather"
bundle = "net.orinks.accessiweather"
url = "http://accessiweather.orinks.net"
author = "Orinks"
author_email = "orin8722@gmail.com"

[tool.briefcase.app.accessiweather]
formal_name = "AccessiWeather"
entry_point = "accessiweather:main"
sources = ["src/accessiweather"]
resources = ["src/accessiweather/resources"]

requires = [
    "toga",
    "httpx>=0.20.0",
    "desktop-notifier",
    # ... other runtime dependencies
]
```

**Platform-Specific:**

```toml
[tool.briefcase.app.accessiweather.windows]
requires = ["pythonnet"]  # Windows-specific dependencies

[tool.briefcase.app.accessiweather.macOS]
universal_build = true  # Intel + Apple Silicon

[tool.briefcase.app.accessiweather.linux.flatpak]
flatpak_runtime = "org.freedesktop.Platform"
flatpak_runtime_version = "24.08"
```

---

## Troubleshooting Builds

### Common Issues

**Issue:** Briefcase create fails with "Template not found"  
**Solution:**
```bash
briefcase create --update  # Force template update
```

**Issue:** Build fails with missing dependencies  
**Solution:** Check `pyproject.toml` `requires` list matches `requirements.txt`

**Issue:** Windows build fails with "Visual Studio not found"  
**Solution:** Install Visual Studio Build Tools 2022

**Issue:** macOS DMG not signed/notarized  
**Solution:** Set up Apple Developer certificates (optional for testing)

**Issue:** Integration tests fail in CI  
**Solution:** Check API rate limits, verify internet connectivity

### Debug Build Issues

```bash
# Verbose output
briefcase build -vv

# Clean build directory
rm -rf build/
briefcase create

# Check logs
cat build/accessiweather/{platform}/app/logs/*.log
```

---

## Deployment Checklist

### Pre-Release

- [ ] All tests passing (`pytest -n auto`)
- [ ] Code formatted (`ruff format .`)
- [ ] Linting clean (`ruff check .`)
- [ ] Version updated in `pyproject.toml`
- [ ] CHANGELOG.md updated
- [ ] Documentation updated (if needed)
- [ ] Manual testing on all platforms
- [ ] Accessibility testing (screen reader)

### Release

- [ ] Tag created and pushed (`git tag v0.x.x`)
- [ ] GitHub Actions builds successful
- [ ] Installers downloadable from GitHub Release
- [ ] Release notes accurate
- [ ] Assets uploaded (MSI, DMG)

### Post-Release

- [ ] Test installers on clean machines
- [ ] Update website (accessiweather.orinks.net)
- [ ] Announce release (if applicable)
- [ ] Monitor GitHub Issues for bug reports
- [ ] Start planning next release

---

## Monitoring & Observability

### Build Monitoring

**GitHub Actions Dashboard:**
- Check workflow runs: `https://github.com/orinks/accessiweather/actions`
- Monitor build times
- Track failure rates

**Artifacts:**
- Build artifacts available for 90 days (GitHub default)
- Download logs for debugging

### Release Metrics

**Track:**
- Download counts per platform (GitHub Insights)
- Installation success rate (user reports)
- Crash reports (if telemetry added)

---

## Distribution Channels

### Official Channels

1. **GitHub Releases** (Primary)
   - URL: https://github.com/orinks/accessiweather/releases
   - Contains: MSI (Windows), DMG (macOS)
   - Nightly builds: Pre-releases

2. **Website** (accessiweather.orinks.net)
   - Direct download links
   - Installation instructions
   - Documentation

### Future Channels (Planned)

- **Microsoft Store** (Windows)
- **Homebrew** (macOS)
- **Snap Store** (Linux)
- **Flatpak** (Linux)

---

## Security Considerations

### Code Signing

**Windows:**
- MSI can be signed with code signing certificate
- Reduces Windows Defender warnings
- Configure in Briefcase: `signing_identity`

**macOS:**
- App bundle must be signed for Gatekeeper
- Notarization required for distribution
- Configure in Briefcase: `codesign_identity`

### Dependency Security

**Automated Scanning:**
- Dependabot (GitHub) - Checks for vulnerable dependencies
- Runs automatically on schedule

**Manual Auditing:**
```bash
# Check for known vulnerabilities
pip audit

# Update dependencies
pip install --upgrade -r requirements.txt
```

---

## Rollback Procedure

### If Release Has Critical Bug

1. **Delete faulty release:**
   ```bash
   # Via GitHub UI: Draft release → Delete
   ```

2. **Delete tag:**
   ```bash
   git tag -d v0.x.x
   git push origin :refs/tags/v0.x.x
   ```

3. **Revert changes:**
   ```bash
   git revert <commit-hash>
   git push origin main
   ```

4. **Create hotfix:**
   ```bash
   git checkout -b hotfix/critical-bug
   # Fix bug
   git commit -m "fix: Critical bug"
   # Bump patch version (e.g., 0.4.3 → 0.4.4)
   # Create new release
   ```

---

## Resources

- **Briefcase Documentation:** https://briefcase.readthedocs.io/
- **GitHub Actions Docs:** https://docs.github.com/en/actions
- **Semantic Versioning:** https://semver.org/
- **WiX Toolset (Windows MSI):** https://wixtoolset.org/

---

## Support

For deployment issues:
- **GitHub Issues:** https://github.com/orinks/accessiweather/issues
- **BeeWare Community:** https://beeware.org/community/
- **Documentation:** [development-guide.md](development-guide.md)
