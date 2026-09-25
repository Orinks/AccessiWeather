# AccessiWeather CI/CD Workflows

This directory contains the GitHub Actions workflows for AccessiWeather. Below is a simplified overview of each workflow and when it runs.

## Core Workflows

### 1. Rust CI (`rust.yml`)
**Purpose**: Validate pull requests that touch `rust/`
**Triggers**: pull requests (`rust/**`), version tags, manual dispatch

**What it does**:
- Runs `cargo fmt`, clippy, the workspace tests, the headless `--check` and a windowed `--smoke` on Linux, Windows and macOS (debug builds)
- Fails when user-facing changes lack a curated `CHANGELOG.md` entry under `## [Unreleased]` (`cargo xtask changelog check`)

---

### 2. Build and Package (`rust-build.yml`)
**Purpose**: Build nightly or tagged release artifacts separately from pull request validation
**Triggers**:
- Nightly schedule at 00:17 UTC (8:17 PM EDT / 7:17 PM EST)
- Version tags
- Manual dispatch (`dry_run` skips publishing)

**What it does**:
- Builds the Rust edition's Windows installer + portable ZIP, macOS ZIP + disk image, and Linux tarball + AppImage with `cargo xtask package`, and smoke-tests them (including the AppImage on Fedora)
- Creates nightly or stable GitHub releases under the asset names the Python edition's updater also reads, so Python installs update into the Rust edition
- Builds release bodies from curated `CHANGELOG.md` entries instead of PR titles
- Skips scheduled nightlies when there are no new curated release notes or explicit build marker

---

### 3. Integration Tests (`rust-integration.yml`)
**Purpose**: Catch weather API changes with live NWS, Open-Meteo and IEM requests
**Triggers**: daily at 06:00 UTC and manual dispatch, never on pull requests

---

### 4. Website Deployment
**Purpose**: Handled by the separate Vercel deployment workflow

The desktop build workflow does not trigger website publishing. It only creates GitHub
release assets that the Vercel site can consume.

---

## Release Workflows

## Workflow Dependencies

`rust.yml` handles validation only.

`rust-build.yml` handles nightly/tagged packaging and release publication.

Website deployment is intentionally separate and owned by the Vercel workflow.

---

## Quick Reference

| Need to... | Use workflow | How |
|------------|--------------|-----|
| Test code changes | `rust.yml` | Automatic on PR |
| Build installers / nightlies | `rust-build.yml` | Nightly, tags, or manual |
| Deploy website | Vercel workflow | Managed outside the desktop build workflow |

---

## For Solo Maintainers

As a solo maintainer, you typically only need to:

1. **Open a PR to `dev`**: `rust.yml` validates formatting, lint, tests and changelog entries
2. **Merge changes to `dev`**: Nightly `rust-build.yml` creates user-facing artifacts when there were user-facing commits
3. **Publish a stable release tag**: `rust-build.yml` creates the release assets; the Vercel workflow owns website deployment

Every user-facing PR needs a `CHANGELOG.md` bullet under `## [Unreleased]`. Commits are checked
locally too: the `commit-msg` hook from `pre-commit install` rejects a user-facing commit when
nothing since `origin/dev` (`origin/main` on `main`) adds one.

**Skipping the gate for non-user-facing work.** The gate flags any change under `src/`,
`installer/`, `soundpacks/`, `rust/crates/` or `rust/packaging/` (the generated
`weather_gov_api_client/` client is excluded). When a
PR is purely internal — refactors, CI, tooling, release plumbing — you have two escape hatches:

- **PR:** add the `skip-changelog` label. The `Check CHANGELOG entry` step is skipped entirely.
- **Commit:** put `Changelog: none` (or `[skip changelog]`) in the commit message. The hook
  passes only when *every* non-merge commit since `origin/dev` carries the marker, so a marker can't
  silently exempt a change set that also contains user-facing work.

Note: `.github/`, `tests/`, and `docs/` are never gated, so CI and test-only changes need no marker.

Scheduled nightlies build when there is at least one newly added Unreleased entry that has not
already shipped in the previous nightly or latest stable notes. If the latest stable release already
contains the scheduled commit, the nightly is skipped. Internal packaged/runtime fixes that should
still ship can opt in with `Nightly: build` or `[nightly build]` in the commit message. Stable
release notes use the matching version section, such as `## [0.6.1]`, and fall back to Unreleased
only when a version section has not been cut yet.

Internal commits do not suppress a scheduled nightly when the same range also contains a new
curated Unreleased entry. For example, merging a user-facing PR with a changelog bullet and then an
internal `Changelog: none` refactor before the next schedule still builds the nightly.

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
- **Build fails**: Check the Rust toolchain, system packages, or packaging setup (`cargo xtask package` runs the same steps locally)
- **Release fails**: Check if release already exists or version conflicts

---

For detailed documentation, see: `/docs/cicd_setup.md`
