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
- Fails when user-facing changes target `dev` without a curated `CHANGELOG.md` entry under `## [Unreleased]`

---

### 2. Build and Package (`build.yml`)
**Purpose**: Build nightly or tagged release artifacts separately from pull request validation
**Triggers**:
- Nightly schedule at 00:17 UTC (8:17 PM EDT / 7:17 PM EST)
- Version tags
- Manual dispatch (with optional version override)

**What it does**:
- Builds Windows installer + portable ZIP, macOS ZIP, and Linux tarball
- Creates nightly or stable GitHub releases
- Builds release bodies from curated `CHANGELOG.md` entries instead of PR titles
- Skips scheduled nightlies when there are no new curated release notes or explicit build marker

---

### 3. Website Deployment
**Purpose**: Handled by the separate Vercel deployment workflow

The desktop build workflow does not trigger website publishing. It only creates GitHub
release assets that the Vercel site can consume.

---

## Release Workflows

## Workflow Dependencies

`ci.yml` handles validation only.

`build.yml` handles nightly/tagged packaging and release publication.

Website deployment is intentionally separate and owned by the Vercel workflow.

---

## Quick Reference

| Need to... | Use workflow | How |
|------------|--------------|-----|
| Test code changes | `ci.yml` | Automatic on PR/push |
| Build installers / nightlies | `build.yml` | Nightly, tags, or manual |
| Deploy website | Vercel workflow | Managed outside the desktop build workflow |

---

## For Solo Maintainers

As a solo maintainer, you typically only need to:

1. **Open a PR to `dev`**: `ci.yml` validates formatting, lint, tests, changelog entries, and diff coverage
2. **Merge changes to `dev`**: Nightly `build.yml` creates user-facing artifacts when there were user-facing commits
3. **Publish a stable release tag**: `build.yml` creates the release assets; the Vercel workflow owns website deployment

Every user-facing PR needs a `CHANGELOG.md` bullet under `## [Unreleased]`. Direct pushes to
`dev` or `main` are checked too, so user-facing commits without an associated PR still need a
curated changelog entry.

**Skipping the gate for non-user-facing work.** The gate flags any change under `src/`,
`installer/`, or `soundpacks/` (the generated `weather_gov_api_client/` client is excluded). When a
PR is purely internal — refactors, CI, tooling, release plumbing — you have two escape hatches:

- **PR:** add the `skip-changelog` label. The `Check CHANGELOG entry` step is skipped entirely.
- **Direct push:** put `Changelog: none` (or `[skip changelog]`) in the commit message. The gate
  passes only when *every* non-merge commit in the range carries the marker, so a marker can't
  silently exempt a change set that also contains user-facing work.

Note: `.github/`, `tests/`, and `docs/` are never gated, so CI and test-only changes need no marker.

Scheduled nightlies build when there is at least one newly added Unreleased entry that has not
already shipped in the previous nightly notes. Internal packaged/runtime fixes that should still
ship can opt in with `Nightly: build` or `[nightly build]` in the commit message. Stable release
notes use the matching version section, such as `## [0.6.1]`, and fall back to Unreleased only when
a version section has not been cut yet.

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
