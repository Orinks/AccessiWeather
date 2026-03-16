# AccessiWeather CI/CD Workflows

This directory contains the GitHub Actions workflows for AccessiWeather. Below is a simplified overview of each workflow and when it runs.

## Core Workflows

### 1. CI (`ci.yml`)
**Purpose**: Validate pull requests and branch pushes with the same core checks, using the fewest visible jobs possible
**Triggers**:
- Push to `main` or `dev` branches
- Pull requests to `main` or `dev`
- Manual dispatch

**What it does**:
- Runs Ruff format and lint checks on the primary Python lane
- Executes the non-integration pytest suite on Python 3.12 and 3.13
- Runs changed-line coverage gating for pull requests in the primary lane
- Posts a non-blocking CHANGELOG reminder in the job summary when `src/` changes target `dev`

---

### 2. Build and Package (`build.yml`)
**Purpose**: Build nightly or tagged release artifacts separately from pull request validation
**Triggers**:
- Nightly schedule
- Version tags
- Manual dispatch (with optional version override)

**What it does**:
- Builds Windows installer + portable ZIP and macOS DMG
- Creates nightly or stable GitHub releases using curated `CHANGELOG.md`
  sections for the public release notes
- Triggers GitHub Pages refresh after a successful release

---

### 3. Update GitHub Pages (`update-pages.yml`)
**Purpose**: Update the GitHub Pages mirror with latest build info
**Triggers**:
- Push to `main`
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

## Workflow Dependencies

`ci.yml` handles validation only.

`build.yml` handles nightly/tagged packaging and release publication.

`update-pages.yml` handles GitHub Pages publication.

`update-wordpress.yml` handles the external WordPress sync after a published release.

---

## Quick Reference

| Need to... | Use workflow | How |
|------------|--------------|-----|
| Test code changes | `ci.yml` | Automatic on PR/push |
| Build installers / nightlies | `build.yml` | Nightly, tags, or manual |
| Update GitHub Pages mirror | `update-pages.yml` | Automatic after build or manual |
| Update WordPress release page | `update-wordpress.yml` | Automatic on release publish or manual |

---

## For Solo Maintainers

As a solo maintainer, you typically only need to:

1. **Open a PR to `dev`**: `ci.yml` validates formatting, lint, tests, and diff coverage
2. **Merge changes to `dev`**: Nightly `build.yml` creates user-facing artifacts when there were user-facing commits
3. **Publish a stable release tag**: `build.yml` creates the release assets, then Pages/WordPress update flows can run

Everything else stays out of the PR path.

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
- **Build fails**: Check Python version, dependencies, or packaging setup
- **Release fails**: Check if release already exists or version conflicts

---

For detailed documentation, see: `/docs/cicd_setup.md`
