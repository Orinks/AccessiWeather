# AccessiWeather CI/CD Workflows

This directory contains the GitHub Actions workflows for AccessiWeather. Below is a simplified overview of each workflow and when it runs.

## Core Workflows

### 1. CI (`windows-ci.yml`)
**Purpose**: Lint, format check, and test the code
**Triggers**:
- Push to `main` or `dev` branches
- Pull requests to `main` or `dev`
- Manual dispatch

**What it does**:
- Runs Ruff format checks
- Runs Ruff linting
- Executes pytest test suite
- Validates installer/build.py smoke test

**Next step**: Triggers `briefcase-build.yml` on success

---

### 2. Build and Package (`briefcase-build.yml`)
**Purpose**: Build Windows installers and portable versions
**Triggers**:
- After successful CI workflow (on `main`, `dev`, or `feature/toga-migration`)
- Manual dispatch (with optional version override)

**What it does**:
- Creates Windows MSI installer
- Creates portable ZIP version
- Generates checksums
- Uploads build artifacts
- Validates all artifacts

**Next step**: Triggers `update-pages.yml` on success

---

### 3. Update GitHub Pages (`update-pages.yml`)
**Purpose**: Update the GitHub Pages mirror with latest build info
**Triggers**:
- After successful Build workflow (on `main` or `dev`)
- After releases are published/edited
- Manual dispatch

**What it does**:
- Fetches latest build information
- Updates the GitHub Pages mirror with version info
- Generates nightly.link URLs
- Deploys to GitHub Pages

---

### 4. Update WordPress release page (`update-wordpress.yml`)
**Purpose**: Update the existing WordPress release page to link directly to the latest public GitHub release assets
**Triggers**:
- When a GitHub release is published
- Manual dispatch

**What it does**:
- Fetches the latest public stable GitHub release
- Picks the primary release asset for the main download button
- Computes GitHub asset download counts
- Updates only the managed section of the existing WordPress page via the standard REST API

---

## Release Workflows

### 5. Official Release (`briefcase-release.yml`)
**Purpose**: Create official releases from main branch
**Triggers**:
- Push to `main` or `feature/toga-migration` (excluding docs)
- Manual dispatch with version input

**What it does**:
- Checks if release already exists
- Builds MSI installer and portable ZIP
- Creates GitHub release (draft)
- Uploads release assets with checksums

**Note**: Creates as **draft** release - you must manually publish it

---

### 6. Beta Release (`beta-release.yml`)
**Purpose**: Create pre-release builds for testing
**Triggers**:
- Push tags matching: `v*-beta.*`, `v*-alpha.*`, `v*-rc.*`, `v*-dev.*`
- Manual dispatch with beta version input

**What it does**:
- Validates beta version format
- Builds MSI installer and portable ZIP
- Creates pre-release with beta-specific notes
- Uploads beta assets with checksums

---

## Testing Workflows

### 7. Test nightly.link (`test-nightly-link.yml`)
**Purpose**: Test nightly.link integration
**Triggers**: Manual dispatch only

**What it does**:
- Tests nightly.link URLs for specified branch
- Generates documentation of available URLs
- Validates artifact accessibility

---

## Workflow Dependencies

```
Push to dev/main
    ↓
windows-ci.yml (CI)
    ↓ (on success)
briefcase-build.yml (Build)
    ↓ (on success)
update-pages.yml (Update Pages)
```

Release workflow runs independently when triggered:
```
Push to main → briefcase-release.yml
Push tag     → beta-release.yml
```

---

## Quick Reference

| Need to... | Use workflow | How |
|------------|--------------|-----|
| Test code changes | `windows-ci.yml` | Automatic on PR/push |
| Build installers | `briefcase-build.yml` | Automatic after CI or manual |
| Update GitHub Pages mirror | `update-pages.yml` | Automatic after build or manual |
| Update WordPress release page | `update-wordpress.yml` | Automatic on release publish or manual |
| Create official release | `briefcase-release.yml` | Push to main or manual |
| Create beta release | `beta-release.yml` | Tag with beta/alpha/rc/dev or manual |
| Test nightly.link | `test-nightly-link.yml` | Manual only |

---

## For Solo Maintainers

As a solo maintainer, you typically only need to:

1. **Push to `dev` branch**: Triggers CI → Build → Pages update automatically
2. **Merge `dev` to `main`**: Triggers release workflow (creates draft)
3. **Review and publish draft release**: Manual step in GitHub UI

Everything else happens automatically! 🎉

---

## Monitoring Workflows

View workflow status at: https://github.com/Orinks/AccessiWeather/actions

- Green checkmark ✅ = Success
- Red X ❌ = Failed
- Yellow dot 🟡 = In progress
- Gray circle ⚪ = Skipped/Cancelled

---

## Troubleshooting

If a workflow fails:

1. Click on the failed workflow run
2. Check the job that failed
3. Review the step logs
4. Look for error messages (usually in red)
5. Fix the issue and push again

Common issues:
- **CI fails**: Usually linting or test failures - run locally first
- **Build fails**: Check Python version, dependencies, or Briefcase setup
- **Release fails**: Check if release already exists or version conflicts

---

For detailed documentation, see: `/docs/cicd_setup.md`
