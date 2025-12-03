# Design Document: GitHub Pages Workflow Fix

## Overview

This design addresses the structural issues in the AccessiWeather GitHub Pages deployment workflow. The solution restructures `update-pages.yml` to use the official GitHub Pages deployment actions (`configure-pages`, `upload-pages-artifact`, `deploy-pages`), fixes nightly.link URL generation, consolidates HTML output to a dedicated directory, and ensures reliable template variable substitution.

The workflow will continue to be triggered by build completions, releases, and manual dispatch, but will now follow GitHub's recommended deployment pattern for static sites.

## Architecture

The updated workflow follows a two-job architecture:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Workflow Triggers                             │
│  • workflow_run (briefcase-build completes on main/dev)         │
│  • release (published/edited)                                    │
│  • workflow_dispatch (manual)                                    │
│  • push to main                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Job 1: build-site                             │
│  1. Checkout repository                                          │
│  2. Setup Python (for API calls and template processing)        │
│  3. Configure Pages (actions/configure-pages)                   │
│  4. Fetch release info (stable + dev/nightly)                   │
│  5. Fetch release notes and recent commits                      │
│  6. Generate HTML from template → _site/index.html              │
│  7. Upload pages artifact (actions/upload-pages-artifact)       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Job 2: deploy                                 │
│  (needs: build-site)                                            │
│  environment: github-pages                                       │
│  1. Deploy to GitHub Pages (actions/deploy-pages)               │
│  2. Output: page_url                                            │
└─────────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. Workflow File Structure

**File:** `.github/workflows/update-pages.yml`

```yaml
# Key structural changes:
jobs:
  build-site:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: actions/configure-pages@v5
      - # ... fetch data and generate HTML ...
      - uses: actions/upload-pages-artifact@v3
        with:
          path: '_site'

  deploy:
    needs: build-site
    runs-on: ubuntu-latest
    permissions:
      pages: write
      id-token: write
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - uses: actions/deploy-pages@v4
```

### 2. nightly.link URL Format

**Corrected URL patterns:**

| Asset Type | URL Pattern |
|------------|-------------|
| Windows Installer (dev) | `https://nightly.link/Orinks/AccessiWeather/workflows/briefcase-build/dev/windows-installer-{version}.zip` |
| Windows Portable (dev) | `https://nightly.link/Orinks/AccessiWeather/workflows/briefcase-build/dev/windows-portable-{version}.zip` |
| macOS Installer (dev) | `https://nightly.link/Orinks/AccessiWeather/workflows/briefcase-build/dev/macOS-installer-{version}.zip` |

**Note:** The workflow name in URLs must match the actual workflow file name (`briefcase-build`), not a display name.

### 3. Output Directory Structure

```
_site/
└── index.html    # Generated from docs/index.template.html
```

The `_site` directory is created during workflow execution and contains only the generated HTML. This directory is then packaged by `upload-pages-artifact` for deployment.

### 4. Template Processing Flow

```
docs/index.template.html
         │
         ▼
┌─────────────────────────┐
│  Variable Substitution  │
│  • {{MAIN_VERSION}}     │
│  • {{MAIN_DATE}}        │
│  • {{DEV_VERSION}}      │
│  • {{DEV_INSTALLER_URL}}│
│  • etc.                 │
└─────────────────────────┘
         │
         ▼
    _site/index.html
```

### 5. API Data Sources

| Data | Source | Fallback |
|------|--------|----------|
| Stable version | GitHub Releases API (non-prerelease) | "Latest Release" |
| Stable assets | Release assets array | GitHub releases page URL |
| Dev version | GitHub Releases API (prerelease) | Workflow runs API |
| Dev assets | Pre-release assets OR nightly.link URLs | Releases page URL |
| Release notes | Release body (markdown → HTML) | "No release notes available" |
| Recent commits | Commits API (dev branch, last 3) | Link to commits page |

## Data Models

### Template Variables

| Variable | Type | Description | Fallback Value |
|----------|------|-------------|----------------|
| `MAIN_VERSION` | string | Stable release version (e.g., "0.9.3") | "Latest Release" |
| `MAIN_DATE` | string | Stable release date (formatted) | "Check GitHub" |
| `MAIN_COMMIT` | string | Commit SHA (7 chars) | "" |
| `MAIN_INSTALLER_URL` | string | Direct MSI download URL | Releases page URL |
| `MAIN_PORTABLE_URL` | string | Direct ZIP download URL | Releases page URL |
| `MAIN_MACOS_INSTALLER_URL` | string | Direct DMG download URL | Releases page URL |
| `MAIN_HAS_RELEASE` | string | "true" or "false" | "false" |
| `MAIN_RELEASE_NOTES` | string | HTML-formatted release notes | Fallback message |
| `DEV_VERSION` | string | Dev/nightly version | "Development (latest)" |
| `DEV_DATE` | string | Dev build date | "Check pre-release page" |
| `DEV_COMMIT` | string | Commit SHA (7 chars) | "" |
| `DEV_RELEASE_URL` | string | Pre-release page URL | Releases page URL |
| `DEV_INSTALLER_URL` | string | nightly.link or release asset URL | Release URL |
| `DEV_PORTABLE_URL` | string | nightly.link or release asset URL | Release URL |
| `DEV_MACOS_INSTALLER_URL` | string | nightly.link or release asset URL | Release URL |
| `DEV_HAS_RELEASE` | string | "true" or "false" | "false" |
| `DEV_RECENT_COMMITS` | string | HTML list of recent commits | "" |
| `LAST_UPDATED` | string | Timestamp of page generation | Current UTC time |

### Workflow Permissions

```yaml
permissions:
  contents: read    # Read repository files
  pages: write      # Deploy to GitHub Pages
  id-token: write   # OIDC token for Pages deployment
```



## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

Based on the prework analysis, the following properties can be verified through testing:

### Property 1: nightly.link URL workflow name correctness
*For any* generated nightly.link URL, the URL path SHALL contain `workflows/briefcase-build/` and SHALL NOT contain `workflows/build/` (without the `briefcase-` prefix).
**Validates: Requirements 2.1**

### Property 2: nightly.link URL format validity
*For any* generated nightly.link URL, the URL SHALL match the pattern `https://nightly.link/Orinks/AccessiWeather/workflows/briefcase-build/{branch}/{artifact-name}.zip` where branch is `main` or `dev` and artifact-name follows the naming convention.
**Validates: Requirements 2.2**

### Property 3: Artifact naming convention
*For any* artifact URL containing a version string, the artifact name SHALL follow the pattern `{platform}-{type}-{version}` where platform is `windows` or `macOS`, type is `installer` or `portable`, and version matches semantic versioning.
**Validates: Requirements 2.3**

### Property 4: Release asset URL extraction
*For any* GitHub release response containing assets with MSI, DMG, or ZIP files, the generated download URLs SHALL be extracted from the `browser_download_url` field of matching assets.
**Validates: Requirements 4.3**

### Property 5: Commit SHA truncation
*For any* displayed commit SHA, the output SHALL be exactly 7 characters (or empty if no commit available), representing the first 7 characters of the full SHA.
**Validates: Requirements 4.5**

### Property 6: Template placeholder substitution completeness
*For any* template string containing `{{VARIABLE}}` placeholders and a corresponding values map, the output string SHALL NOT contain any `{{` or `}}` sequences.
**Validates: Requirements 6.1, 6.3**

### Property 7: Empty value fallback handling
*For any* template variable with an empty, null, or undefined value, the substitution SHALL replace the placeholder with the defined fallback value (not an empty string or the original placeholder).
**Validates: Requirements 6.2**

## Error Handling

### API Failures

| Scenario | Handling |
|----------|----------|
| GitHub Releases API returns 404 | Use fallback values ("No releases available") |
| GitHub Releases API rate limited | Log warning, use cached/fallback values |
| Release has no assets | Use releases page URL as fallback |
| Workflow runs API fails | Fall back to release-based URLs |
| Network timeout | Retry once, then use fallbacks |

### Template Processing Errors

| Scenario | Handling |
|----------|----------|
| Template file not found | Fail workflow with clear error message |
| Variable value is null/undefined | Substitute with defined fallback value |
| Unsubstituted placeholders remain | Log warning, continue with partial substitution |
| HTML generation fails | Fail workflow, do not deploy broken page |

### Deployment Errors

| Scenario | Handling |
|----------|----------|
| Pages artifact upload fails | Fail workflow, no deployment |
| Deploy action fails | Workflow fails, previous deployment remains |
| Concurrent deployment conflict | Concurrency group ensures serialization |

## Testing Strategy

### Dual Testing Approach

This feature requires both unit tests for template processing logic and workflow validation tests for the GitHub Actions configuration.

### Unit Testing

Unit tests will cover the template substitution logic that can be extracted into testable functions:

1. **URL Generation Tests**
   - Test nightly.link URL construction with various versions
   - Test fallback URL generation when assets are missing
   - Test artifact name pattern matching

2. **Template Substitution Tests**
   - Test all placeholders are replaced
   - Test fallback values are used for empty inputs
   - Test no `{{` patterns remain after substitution

3. **Data Extraction Tests**
   - Test release asset URL extraction from API responses
   - Test commit SHA truncation
   - Test date formatting

### Property-Based Testing

Property-based tests will use **Hypothesis** (Python) to verify the correctness properties defined above.

Each property-based test MUST:
- Run a minimum of 100 iterations
- Be tagged with a comment referencing the correctness property: `# Feature: github-pages-workflow-fix, Property {number}: {property_text}`
- Generate random but valid inputs within the expected domain

**Test File:** `tests/test_pages_workflow_properties.py`

### Workflow Validation Tests

Since GitHub Actions workflows are YAML configuration, validation will be done through:

1. **YAML Schema Validation** - Verify workflow structure is valid
2. **Static Analysis** - Check for required actions and configurations
3. **Integration Testing** - Manual verification via workflow dispatch

### Test Coverage Matrix

| Requirement | Unit Test | Property Test | Workflow Validation |
|-------------|-----------|---------------|---------------------|
| 1.1-1.4 | - | - | ✓ (YAML structure) |
| 2.1-2.3 | ✓ | ✓ (Properties 1-3) | - |
| 3.1-3.3 | - | - | ✓ (YAML structure) |
| 4.1-4.5 | ✓ | ✓ (Properties 4-5) | - |
| 5.1-5.5 | - | - | ✓ (YAML structure) |
| 6.1-6.4 | ✓ | ✓ (Properties 6-7) | - |
