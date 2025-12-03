# Requirements Document

## Introduction

This specification addresses issues with the GitHub Pages deployment workflow for AccessiWeather. The current workflow (`update-pages.yml`) generates an HTML download page with version information, changelog, and binary download links for both stable releases and nightly/dev builds. However, the deployment pipeline has structural issues preventing reliable page updates, including missing deployment steps, incorrect nightly.link URLs, and conflicting HTML files.

## Glossary

- **GitHub Pages**: GitHub's static site hosting service that serves content from a repository
- **nightly.link**: A third-party service that provides direct download links to GitHub Actions artifacts without requiring authentication
- **Stable Release**: Official releases published from the main branch with version tags (e.g., v0.9.3)
- **Nightly/Dev Build**: Pre-release builds from the dev branch, typically created daily when changes exist
- **Workflow Run Event**: A GitHub Actions trigger that fires when another workflow completes
- **Pages Artifact**: A specially formatted artifact (gzip-compressed tar) required by GitHub Pages deployment actions

## Requirements

### Requirement 1: Proper GitHub Pages Deployment Pipeline

**User Story:** As a repository maintainer, I want the GitHub Pages workflow to use the official deployment actions, so that the download page deploys reliably after builds complete.

#### Acceptance Criteria

1. WHEN the update-pages workflow runs THEN the System SHALL use `actions/configure-pages` to set up the Pages environment
2. WHEN static content is generated THEN the System SHALL use `actions/upload-pages-artifact` to package the site for deployment
3. WHEN the pages artifact is uploaded THEN the System SHALL use `actions/deploy-pages` to publish the site
4. WHEN deploying to GitHub Pages THEN the System SHALL configure the `github-pages` environment with the deployment URL output
5. WHEN the workflow completes successfully THEN the System SHALL have the updated download page accessible at the GitHub Pages URL

### Requirement 2: Correct nightly.link URL Generation

**User Story:** As a user visiting the download page, I want the development build download links to work correctly, so that I can download the latest dev builds without errors.

#### Acceptance Criteria

1. WHEN generating dev build download URLs THEN the System SHALL reference the workflow file name `briefcase-build` (not `build`)
2. WHEN constructing nightly.link URLs THEN the System SHALL use the format `https://nightly.link/Orinks/AccessiWeather/workflows/briefcase-build/{branch}/{artifact-name}.zip`
3. WHEN the artifact name includes a version THEN the System SHALL use the pattern `windows-installer-{version}` and `windows-portable-{version}`
4. WHEN macOS artifacts exist THEN the System SHALL include nightly.link URLs for `macOS-installer-{version}` artifacts

### Requirement 3: Consolidated HTML Output Structure

**User Story:** As a repository maintainer, I want a single source of truth for the download page, so that there are no conflicts between static and generated HTML files.

#### Acceptance Criteria

1. WHEN the workflow generates HTML THEN the System SHALL output to a dedicated `_site` directory (not the repository root)
2. WHEN preparing the pages artifact THEN the System SHALL include only the generated `index.html` and any required assets from the `_site` directory
3. WHEN the workflow runs THEN the System SHALL NOT modify the `docs/index.html` file in the repository
4. THE template file `docs/index.template.html` SHALL remain the single source for page generation

### Requirement 4: Reliable Build Information Fetching

**User Story:** As a user visiting the download page, I want to see accurate version information and download links for both stable and dev releases, so that I can choose the appropriate version to download.

#### Acceptance Criteria

1. WHEN fetching stable release information THEN the System SHALL query the GitHub Releases API for non-prerelease, non-draft releases
2. WHEN fetching dev/nightly release information THEN the System SHALL query for prerelease releases OR fall back to latest successful workflow run artifacts
3. WHEN a release has binary assets (MSI, DMG, ZIP) THEN the System SHALL extract and display direct download URLs from the release assets
4. WHEN no release assets exist THEN the System SHALL display appropriate fallback messaging and link to the releases page
5. WHEN displaying version information THEN the System SHALL show version number, build date, and commit SHA (truncated to 7 characters)

### Requirement 5: Workflow Trigger Reliability

**User Story:** As a repository maintainer, I want the pages to update automatically after successful builds and releases, so that users always see current download information.

#### Acceptance Criteria

1. WHEN the `briefcase-build` workflow completes successfully on main or dev branches THEN the System SHALL trigger the pages update workflow
2. WHEN a GitHub release is published or edited THEN the System SHALL trigger the pages update workflow
3. WHEN manually dispatched THEN the System SHALL allow forcing an update with branch selection options
4. WHEN the triggering workflow fails THEN the System SHALL NOT attempt to deploy pages
5. WHEN multiple workflow runs are queued THEN the System SHALL use concurrency controls to prevent conflicting deployments

### Requirement 6: Template Variable Substitution

**User Story:** As a repository maintainer, I want all template placeholders to be reliably substituted, so that the deployed page shows actual data instead of placeholder text.

#### Acceptance Criteria

1. WHEN generating HTML from the template THEN the System SHALL substitute all `{{VARIABLE}}` placeholders with actual values
2. WHEN a variable value is empty or unavailable THEN the System SHALL substitute with an appropriate fallback value (not leave the placeholder)
3. WHEN substitution completes THEN the System SHALL verify no `{{` patterns remain in the output HTML
4. IF unsubstituted placeholders are detected THEN the System SHALL log a warning but continue deployment with fallback values
