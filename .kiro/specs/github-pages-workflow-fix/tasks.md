# Implementation Plan

- [x] 1. Create template processing utility module





  - [x] 1.1 Create `scripts/pages_utils.py` with URL generation functions

    - Implement `generate_nightly_link_url(branch, artifact_type, version)` function
    - Implement `extract_asset_url(release_assets, asset_type)` function


    - Implement `truncate_commit_sha(sha, length=7)` function

    - _Requirements: 2.1, 2.2, 2.3, 4.3, 4.5_
  - [x] 1.2 Write property tests for URL generation

    - **Property 1: nightly.link URL workflow name correctness**

    - **Property 2: nightly.link URL format validity**
    - **Property 3: Artifact naming convention**
    - **Validates: Requirements 2.1, 2.2, 2.3**




  - [ ] 1.3 Implement template substitution function
    - Create `substitute_template(template_content, variables, fallbacks)` function


    - Ensure all `{{VARIABLE}}` patterns are replaced
    - Apply fallback values for empty/null variables
    - _Requirements: 6.1, 6.2, 6.3_









  - [ ] 1.4 Write property tests for template substitution
    - **Property 6: Template placeholder substitution completeness**
    - **Property 7: Empty value fallback handling**


    - **Validates: Requirements 6.1, 6.2, 6.3**
  - [ ] 1.5 Write property tests for data extraction
    - **Property 4: Release asset URL extraction**
    - **Property 5: Commit SHA truncation**

    - **Validates: Requirements 4.3, 4.5**


- [x] 2. Checkpoint - Ensure all tests pass

  - Ensure all tests pass, ask the user if questions arise.


- [ ] 3. Update the GitHub Pages workflow structure
  - [x] 3.1 Restructure `update-pages.yml` with two-job architecture

    - Rename existing job to `build-site`
    - Add `actions/configure-pages@v5` step after checkout
    - Update HTML generation to output to `_site/index.html`

    - Add `actions/upload-pages-artifact@v3` with path `_site`

    - _Requirements: 1.1, 1.2, 3.1, 3.2_
  - [ ] 3.2 Add deploy job to workflow
    - Create `deploy` job with `needs: build-site`
    - Configure `github-pages` environment with URL output


    - Add `actions/deploy-pages@v4` step
    - Set proper permissions (pages: write, id-token: write)

    - _Requirements: 1.3, 1.4_
  - [ ] 3.3 Update workflow triggers and conditions
    - Verify `workflow_run` trigger references `Build and Package with Briefcase`



    - Ensure condition checks `github.event.workflow_run.conclusion == 'success'`
    - Verify concurrency group configuration
    - _Requirements: 5.1, 5.4, 5.5_



- [ ] 4. Fix nightly.link URL generation in workflow
  - [ ] 4.1 Update `get_build_info` function in workflow
    - Change URL pattern from `workflows/build/` to `workflows/briefcase-build/`

    - Update artifact name patterns to match actual artifact names

    - Add macOS artifact URL generation
    - _Requirements: 2.1, 2.2, 2.3, 2.4_
  - [ ] 4.2 Update `get_pre_release_info` function
    - Fix installer URL extraction to look for `.msi` files
    - Fix portable URL extraction to look for `portable` in name
    - Add macOS DMG URL extraction
    - _Requirements: 4.3_

  - [x] 4.3 Update fallback URL generation

    - Ensure fallback URLs point to releases page when assets unavailable




    - Add appropriate fallback values for all URL variables
    - _Requirements: 4.4_




- [x] 5. Update HTML template and generation

  - [x] 5.1 Update `docs/index.template.html` with corrected URL patterns



    - Fix JavaScript `buildInfo` object URL patterns
    - Ensure nightly.link URLs use `briefcase-build` workflow name



    - _Requirements: 2.1, 2.2_
  - [x] 5.2 Update HTML generation step in workflow

    - Change output path from `index.html` (root) to `_site/index.html`
    - Create `_site` directory before generating HTML


    - Update verification step to check `_site/index.html`

    - _Requirements: 3.1, 3.2_
  - [ ] 5.3 Add substitution verification step
    - Add check for remaining `{{` patterns in generated HTML
    - Log warning if unsubstituted placeholders found

    - Apply fallback values and continue deployment
    - _Requirements: 6.3, 6.4_

- [ ] 6. Clean up conflicting files
  - [ ] 6.1 Remove or update `docs/index.html`
    - Either delete `docs/index.html` (static file with placeholders)
    - Or add comment indicating it's superseded by workflow-generated page
    - _Requirements: 3.3, 3.4_

- [ ] 7. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 8. Final validation
  - [ ] 8.1 Validate workflow YAML structure
    - Verify all required actions are present with correct versions
    - Verify permissions are correctly set
    - Verify environment configuration is correct
    - _Requirements: 1.1, 1.2, 1.3, 1.4_
  - [ ] 8.2 Write workflow structure validation tests
    - Test YAML contains required action references
    - Test permissions include pages:write and id-token:write
    - Test environment is configured as github-pages
    - _Requirements: 1.1-1.4, 5.1-5.5_
