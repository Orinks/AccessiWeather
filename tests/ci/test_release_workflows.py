"""Tests for release workflow configurations."""

from pathlib import Path

import pytest
import yaml


def _get_triggers(workflow: dict) -> dict:
    """Get workflow triggers, handling 'on' vs True key issue."""
    return workflow.get("on") or workflow.get(True, {})


@pytest.fixture
def stable_release_workflow():
    """Load the stable release workflow (briefcase-release.yml)."""
    path = Path(__file__).parent.parent.parent / ".github" / "workflows" / "briefcase-release.yml"
    with open(path) as f:
        return yaml.safe_load(f)


@pytest.fixture
def nightly_workflow():
    """Load the nightly release workflow (nightly-release.yml)."""
    path = Path(__file__).parent.parent.parent / ".github" / "workflows" / "nightly-release.yml"
    with open(path) as f:
        return yaml.safe_load(f)


@pytest.mark.ci
class TestStableReleaseWorkflow:
    """Tests for the stable release workflow (briefcase-release.yml)."""

    def test_triggers_on_build_completion(self, stable_release_workflow):
        """Verify workflow triggers on build workflow completion."""
        triggers = _get_triggers(stable_release_workflow)
        assert "workflow_run" in triggers
        workflow_run = triggers["workflow_run"]
        assert "Build and Package with Briefcase" in workflow_run["workflows"]
        assert "completed" in workflow_run["types"]

    def test_only_main_branch(self, stable_release_workflow):
        """Verify workflow only triggers for main branch."""
        triggers = _get_triggers(stable_release_workflow)
        workflow_run = triggers["workflow_run"]
        assert "branches" in workflow_run
        assert "main" in workflow_run["branches"]

    def test_has_write_permissions(self, stable_release_workflow):
        """Verify workflow has write permissions for contents."""
        permissions = stable_release_workflow.get("permissions", {})
        assert permissions.get("contents") == "write"

    def test_has_actions_read_permission(self, stable_release_workflow):
        """Verify workflow has read permissions for actions (artifact download)."""
        permissions = stable_release_workflow.get("permissions", {})
        assert permissions.get("actions") == "read"

    def test_has_workflow_dispatch(self, stable_release_workflow):
        """Verify workflow supports manual dispatch."""
        triggers = _get_triggers(stable_release_workflow)
        assert "workflow_dispatch" in triggers

    def test_downloads_artifacts_correctly(self, stable_release_workflow):
        """Verify workflow downloads artifacts with correct patterns."""
        steps = stable_release_workflow["jobs"]["release"]["steps"]
        download_steps = [s for s in steps if "download-artifact" in s.get("uses", "")]
        assert len(download_steps) >= 2

        patterns_found = []
        for step in download_steps:
            pattern = step.get("with", {}).get("pattern", "")
            patterns_found.append(pattern)

        assert "*-installer-*" in patterns_found
        assert "windows-portable-*" in patterns_found

    def test_downloads_use_merge_multiple(self, stable_release_workflow):
        """Verify artifact downloads use merge-multiple option."""
        steps = stable_release_workflow["jobs"]["release"]["steps"]
        download_steps = [s for s in steps if "download-artifact" in s.get("uses", "")]
        for step in download_steps:
            assert step.get("with", {}).get("merge-multiple") is True

    def test_downloads_use_run_id(self, stable_release_workflow):
        """Verify artifact downloads reference the build run ID."""
        steps = stable_release_workflow["jobs"]["release"]["steps"]
        download_steps = [s for s in steps if "download-artifact" in s.get("uses", "")]
        for step in download_steps:
            run_id = step.get("with", {}).get("run-id", "")
            assert "build-run.outputs.run_id" in run_id

    def test_creates_release_with_proper_naming(self, stable_release_workflow):
        """Verify release is created with proper naming convention."""
        steps = stable_release_workflow["jobs"]["release"]["steps"]
        create_release_step = next((s for s in steps if s.get("name") == "Create Release"), None)
        assert create_release_step is not None
        run_content = create_release_step.get("run", "")
        assert "AccessiWeather v${VERSION}" in run_content
        assert "gh release create" in run_content

    def test_release_uses_gh_cli(self, stable_release_workflow):
        """Verify release creation uses GitHub CLI."""
        steps = stable_release_workflow["jobs"]["release"]["steps"]
        create_release_step = next((s for s in steps if s.get("name") == "Create Release"), None)
        run_content = create_release_step.get("run", "")
        assert "gh release create" in run_content

    def test_release_uses_notes_file(self, stable_release_workflow):
        """Verify release uses notes file from changelog extraction."""
        steps = stable_release_workflow["jobs"]["release"]["steps"]
        create_release_step = next((s for s in steps if s.get("name") == "Create Release"), None)
        run_content = create_release_step.get("run", "")
        assert "--notes-file" in run_content
        assert "release-notes.md" in run_content

    def test_version_extraction_step_exists(self, stable_release_workflow):
        """Verify version is extracted from pyproject.toml."""
        steps = stable_release_workflow["jobs"]["release"]["steps"]
        version_step = next((s for s in steps if s.get("name") == "Get version"), None)
        assert version_step is not None
        assert "pyproject.toml" in version_step.get("run", "")
        assert "tomllib" in version_step.get("run", "")

    def test_version_step_has_output_id(self, stable_release_workflow):
        """Verify version step has proper output ID."""
        steps = stable_release_workflow["jobs"]["release"]["steps"]
        version_step = next((s for s in steps if s.get("name") == "Get version"), None)
        assert version_step.get("id") == "version"
        assert "GITHUB_OUTPUT" in version_step.get("run", "")

    def test_tag_check_exists(self, stable_release_workflow):
        """Verify tag existence check step exists."""
        steps = stable_release_workflow["jobs"]["release"]["steps"]
        tag_step = next((s for s in steps if "tag" in s.get("name", "").lower()), None)
        assert tag_step is not None
        run_content = tag_step.get("run", "")
        assert "git fetch --tags" in run_content
        assert "git rev-parse" in run_content

    def test_tag_check_has_output(self, stable_release_workflow):
        """Verify tag check step has publish output."""
        steps = stable_release_workflow["jobs"]["release"]["steps"]
        tag_step = next((s for s in steps if "tag" in s.get("name", "").lower()), None)
        run_content = tag_step.get("run", "")
        assert "publish=true" in run_content
        assert "publish=false" in run_content

    def test_changelog_extraction_exists(self, stable_release_workflow):
        """Verify changelog extraction step exists."""
        steps = stable_release_workflow["jobs"]["release"]["steps"]
        changelog_step = next((s for s in steps if "changelog" in s.get("name", "").lower()), None)
        assert changelog_step is not None

    def test_changelog_extraction_logic(self, stable_release_workflow):
        """Verify changelog extraction uses regex to find version section."""
        steps = stable_release_workflow["jobs"]["release"]["steps"]
        changelog_step = next((s for s in steps if "changelog" in s.get("name", "").lower()), None)
        run_content = changelog_step.get("run", "")
        assert "CHANGELOG.md" in run_content
        assert "re.search" in run_content or "pattern" in run_content

    def test_changelog_fallback_to_unreleased(self, stable_release_workflow):
        """Verify changelog extraction has fallback to Unreleased section."""
        steps = stable_release_workflow["jobs"]["release"]["steps"]
        changelog_step = next(
            (s for s in steps if "Extract release notes" in s.get("name", "")), None
        )
        run_content = changelog_step.get("run", "")
        assert "Unreleased" in run_content

    def test_release_notes_saved_to_file(self, stable_release_workflow):
        """Verify release notes are saved to a file."""
        steps = stable_release_workflow["jobs"]["release"]["steps"]
        save_step = next((s for s in steps if "Save release notes" in s.get("name", "")), None)
        assert save_step is not None
        run_content = save_step.get("run", "")
        assert "release-notes.md" in run_content

    def test_checksum_generation(self, stable_release_workflow):
        """Verify checksums are generated for release assets."""
        steps = stable_release_workflow["jobs"]["release"]["steps"]
        prepare_step = next(
            (s for s in steps if "Prepare release assets" in s.get("name", "")), None
        )
        assert prepare_step is not None
        assert "sha256sum" in prepare_step.get("run", "")

    def test_asset_renaming(self, stable_release_workflow):
        """Verify assets are renamed with version."""
        steps = stable_release_workflow["jobs"]["release"]["steps"]
        prepare_step = next(
            (s for s in steps if "Prepare release assets" in s.get("name", "")), None
        )
        run_content = prepare_step.get("run", "")
        assert "AccessiWeather-${VERSION}.msi" in run_content
        assert "AccessiWeather-${VERSION}.dmg" in run_content

    def test_release_deletes_existing(self, stable_release_workflow):
        """Verify existing release is deleted before creating new one."""
        steps = stable_release_workflow["jobs"]["release"]["steps"]
        create_step = next((s for s in steps if s.get("name") == "Create Release"), None)
        run_content = create_step.get("run", "")
        assert "gh release delete" in run_content

    def test_runs_on_ubuntu(self, stable_release_workflow):
        """Verify release job runs on ubuntu-latest."""
        job = stable_release_workflow["jobs"]["release"]
        assert job.get("runs-on") == "ubuntu-latest"

    def test_release_job_condition(self, stable_release_workflow):
        """Verify release job has proper condition for workflow_run success."""
        job = stable_release_workflow["jobs"]["release"]
        condition = job.get("if", "")
        assert "workflow_dispatch" in condition
        assert "workflow_run.conclusion" in condition
        assert "success" in condition

    def test_get_build_run_id_step(self, stable_release_workflow):
        """Verify step to get build run ID exists for artifact download."""
        steps = stable_release_workflow["jobs"]["release"]["steps"]
        run_id_step = next((s for s in steps if "build run" in s.get("name", "").lower()), None)
        assert run_id_step is not None
        run_content = run_id_step.get("run", "")
        assert "workflow_run.id" in run_content


@pytest.mark.ci
class TestNightlyWorkflow:
    """Tests for the nightly release workflow (nightly-release.yml)."""

    def test_schedule_trigger_valid(self, nightly_workflow):
        """Verify cron schedule is valid (30 3 * * *)."""
        triggers = _get_triggers(nightly_workflow)
        assert "schedule" in triggers
        cron_entries = triggers["schedule"]
        assert len(cron_entries) >= 1
        cron = cron_entries[0]["cron"]
        assert cron == "30 3 * * *"

    def test_cron_format_valid(self, nightly_workflow):
        """Verify cron format has 5 fields (minute hour day month weekday)."""
        triggers = _get_triggers(nightly_workflow)
        cron = triggers["schedule"][0]["cron"]
        parts = cron.split()
        assert len(parts) == 5

    def test_cron_time_is_early_morning_utc(self, nightly_workflow):
        """Verify cron runs at 3:30 AM UTC (reasonable for nightly)."""
        triggers = _get_triggers(nightly_workflow)
        cron = triggers["schedule"][0]["cron"]
        parts = cron.split()
        minute, hour = int(parts[0]), int(parts[1])
        assert minute == 30
        assert hour == 3

    def test_change_detection_job_exists(self, nightly_workflow):
        """Verify change detection job exists."""
        jobs = nightly_workflow["jobs"]
        assert "prepare" in jobs
        prepare_job = jobs["prepare"]
        assert "Check for changes" in prepare_job.get("name", "")

        steps = prepare_job["steps"]
        change_step = next((s for s in steps if "changes" in s.get("name", "").lower()), None)
        assert change_step is not None

    def test_change_detection_checks_src_directory(self, nightly_workflow):
        """Verify change detection specifically checks src/ directory."""
        prepare_job = nightly_workflow["jobs"]["prepare"]
        steps = prepare_job["steps"]
        change_step = next((s for s in steps if "changes" in s.get("name", "").lower()), None)
        run_content = change_step.get("run", "")
        assert "src/" in run_content
        assert "git diff" in run_content

    def test_change_detection_checks_existing_tags(self, nightly_workflow):
        """Verify change detection checks if HEAD already has nightly tag."""
        prepare_job = nightly_workflow["jobs"]["prepare"]
        steps = prepare_job["steps"]
        change_step = next((s for s in steps if "changes" in s.get("name", "").lower()), None)
        run_content = change_step.get("run", "")
        assert "nightly-" in run_content
        assert "tag" in run_content

    def test_change_detection_outputs(self, nightly_workflow):
        """Verify change detection outputs are defined."""
        prepare_job = nightly_workflow["jobs"]["prepare"]
        outputs = prepare_job.get("outputs", {})
        assert "changed" in outputs
        assert "version" in outputs

    def test_build_matrix_includes_windows_and_macos(self, nightly_workflow):
        """Verify build matrix includes windows and macos."""
        build_job = nightly_workflow["jobs"]["build"]
        strategy = build_job.get("strategy", {})
        matrix = strategy.get("matrix", {})
        includes = matrix.get("include", [])

        platforms = [entry.get("platform") for entry in includes]
        assert "windows" in platforms
        assert "macOS" in platforms

    def test_build_matrix_os_runners(self, nightly_workflow):
        """Verify correct OS runners are used."""
        build_job = nightly_workflow["jobs"]["build"]
        includes = build_job["strategy"]["matrix"]["include"]

        os_map = {entry["platform"]: entry["os"] for entry in includes}
        assert os_map["windows"] == "windows-latest"
        assert os_map["macOS"] == "macos-latest"

    def test_build_matrix_installer_patterns(self, nightly_workflow):
        """Verify build matrix includes correct installer patterns."""
        build_job = nightly_workflow["jobs"]["build"]
        includes = build_job["strategy"]["matrix"]["include"]

        pattern_map = {entry["platform"]: entry["installer_pattern"] for entry in includes}
        assert pattern_map["windows"] == "*.msi"
        assert pattern_map["macOS"] == "*.dmg"

    def test_build_matrix_fail_fast_disabled(self, nightly_workflow):
        """Verify fail-fast is disabled so all platforms build even if one fails."""
        build_job = nightly_workflow["jobs"]["build"]
        strategy = build_job.get("strategy", {})
        assert strategy.get("fail-fast") is False

    def test_prerelease_flag_set(self, nightly_workflow):
        """Verify prerelease flag is set in release creation."""
        release_job = nightly_workflow["jobs"]["nightly-release"]
        steps = release_job["steps"]
        create_step = next((s for s in steps if "Prerelease" in s.get("name", "")), None)
        assert create_step is not None
        run_content = create_step.get("run", "")
        assert "--prerelease" in run_content

    def test_release_uses_generate_notes(self, nightly_workflow):
        """Verify nightly release uses --generate-notes for automatic notes."""
        release_job = nightly_workflow["jobs"]["nightly-release"]
        steps = release_job["steps"]
        create_step = next((s for s in steps if "Prerelease" in s.get("name", "")), None)
        run_content = create_step.get("run", "")
        assert "--generate-notes" in run_content

    def test_targets_dev_branch(self, nightly_workflow):
        """Verify nightly builds target the dev branch."""
        prepare_job = nightly_workflow["jobs"]["prepare"]
        checkout_step = next(
            (s for s in prepare_job["steps"] if "checkout" in s.get("uses", "").lower()), None
        )
        assert checkout_step is not None
        assert checkout_step.get("with", {}).get("ref") == "dev"

    def test_all_jobs_target_dev_branch(self, nightly_workflow):
        """Verify all jobs with checkout target dev branch."""
        for job_name, job in nightly_workflow["jobs"].items():
            checkout_step = next(
                (s for s in job.get("steps", []) if "checkout" in s.get("uses", "").lower()), None
            )
            if checkout_step and "ref" in checkout_step.get("with", {}):
                assert checkout_step["with"]["ref"] == "dev", f"Job {job_name} should target dev"

    def test_release_targets_dev(self, nightly_workflow):
        """Verify the release is created targeting dev branch."""
        release_job = nightly_workflow["jobs"]["nightly-release"]
        steps = release_job["steps"]
        create_step = next((s for s in steps if "Prerelease" in s.get("name", "")), None)
        run_content = create_step.get("run", "")
        assert "--target dev" in run_content

    def test_concurrency_prevents_duplicate_runs(self, nightly_workflow):
        """Verify concurrency settings prevent duplicate runs."""
        concurrency = nightly_workflow.get("concurrency", {})
        assert concurrency.get("group") == "nightly-release"
        assert concurrency.get("cancel-in-progress") is True

    def test_has_workflow_dispatch(self, nightly_workflow):
        """Verify workflow supports manual dispatch."""
        triggers = _get_triggers(nightly_workflow)
        assert "workflow_dispatch" in triggers

    def test_has_write_permissions(self, nightly_workflow):
        """Verify workflow has write permissions."""
        permissions = nightly_workflow.get("permissions", {})
        assert permissions.get("contents") == "write"

    def test_has_actions_write_permission(self, nightly_workflow):
        """Verify workflow has actions write permission."""
        permissions = nightly_workflow.get("permissions", {})
        assert permissions.get("actions") == "write"

    def test_artifact_retention_days(self, nightly_workflow):
        """Verify artifacts have appropriate retention period."""
        build_job = nightly_workflow["jobs"]["build"]
        upload_steps = [s for s in build_job["steps"] if "upload-artifact" in s.get("uses", "")]
        for step in upload_steps:
            retention = step.get("with", {}).get("retention-days")
            assert retention == 7

    def test_build_depends_on_prepare(self, nightly_workflow):
        """Verify build job depends on prepare job."""
        build_job = nightly_workflow["jobs"]["build"]
        assert "prepare" in build_job.get("needs", [])

    def test_release_depends_on_build(self, nightly_workflow):
        """Verify release job depends on build job."""
        release_job = nightly_workflow["jobs"]["nightly-release"]
        needs = release_job.get("needs", [])
        assert "build" in needs
        assert "prepare" in needs

    def test_skip_if_no_changes(self, nightly_workflow):
        """Verify build is skipped if no changes detected."""
        build_job = nightly_workflow["jobs"]["build"]
        condition = build_job.get("if", "")
        assert "changed" in condition
        assert "true" in condition

    def test_release_skipped_if_no_changes(self, nightly_workflow):
        """Verify release is skipped if no changes detected."""
        release_job = nightly_workflow["jobs"]["nightly-release"]
        condition = release_job.get("if", "")
        assert "changed" in condition
        assert "true" in condition

    def test_nightly_tag_naming(self, nightly_workflow):
        """Verify nightly tag uses date-based naming."""
        release_job = nightly_workflow["jobs"]["nightly-release"]
        steps = release_job["steps"]
        create_step = next((s for s in steps if "Prerelease" in s.get("name", "")), None)
        run_content = create_step.get("run", "")
        assert "nightly-$(date" in run_content or "nightly-" in run_content

    def test_deletes_existing_nightly_release(self, nightly_workflow):
        """Verify existing nightly release is deleted for same-day reruns."""
        release_job = nightly_workflow["jobs"]["nightly-release"]
        steps = release_job["steps"]
        create_step = next((s for s in steps if "Prerelease" in s.get("name", "")), None)
        run_content = create_step.get("run", "")
        assert "gh release delete" in run_content
        assert "--cleanup-tag" in run_content

    def test_portable_zip_windows_only(self, nightly_workflow):
        """Verify portable ZIP is created only for Windows."""
        build_job = nightly_workflow["jobs"]["build"]
        steps = build_job["steps"]
        portable_step = next((s for s in steps if "portable" in s.get("name", "").lower()), None)
        assert portable_step is not None
        assert portable_step.get("if") == "matrix.platform == 'windows'"

    def test_checksum_generation(self, nightly_workflow):
        """Verify checksums are generated for nightly assets."""
        release_job = nightly_workflow["jobs"]["nightly-release"]
        steps = release_job["steps"]
        prepare_step = next((s for s in steps if "Prepare assets" in s.get("name", "")), None)
        assert prepare_step is not None
        run_content = prepare_step.get("run", "")
        assert "sha256sum" in run_content

    def test_env_variables_set(self, nightly_workflow):
        """Verify required environment variables are set."""
        env = nightly_workflow.get("env", {})
        assert env.get("FORCE_COLOR") == "0"
        assert env.get("PYTHONUTF8") == "1"
        assert "PYTHON_VERSION" in env

    def test_default_shell_is_bash(self, nightly_workflow):
        """Verify default shell is bash for cross-platform consistency."""
        defaults = nightly_workflow.get("defaults", {})
        run_defaults = defaults.get("run", {})
        assert run_defaults.get("shell") == "bash"

    def test_prepare_uses_fetch_depth_zero(self, nightly_workflow):
        """Verify prepare checkout uses fetch-depth 0 for git history."""
        prepare_job = nightly_workflow["jobs"]["prepare"]
        checkout_step = next(
            (s for s in prepare_job["steps"] if "checkout" in s.get("uses", "").lower()), None
        )
        assert checkout_step.get("with", {}).get("fetch-depth") == 0

    def test_briefcase_build_steps(self, nightly_workflow):
        """Verify build job has all briefcase steps."""
        build_job = nightly_workflow["jobs"]["build"]
        steps = build_job["steps"]
        step_names = [s.get("name", "") for s in steps]

        assert any("scaffold" in name.lower() or "create" in name.lower() for name in step_names)
        assert any("build" in name.lower() for name in step_names)
        assert any("package" in name.lower() for name in step_names)


@pytest.mark.ci
class TestWorkflowCommonPatterns:
    """Tests for common patterns across release workflows."""

    def test_all_workflows_have_names(self, stable_release_workflow, nightly_workflow):
        """Verify all workflows have descriptive names."""
        assert "name" in stable_release_workflow
        assert "name" in nightly_workflow

    def test_workflow_names_are_descriptive(self, stable_release_workflow, nightly_workflow):
        """Verify workflow names are descriptive."""
        assert "Release" in stable_release_workflow["name"]
        assert "Nightly" in nightly_workflow["name"]

    def test_all_use_checkout_action(self, stable_release_workflow, nightly_workflow):
        """Verify all workflows use checkout action."""
        for workflow in [stable_release_workflow, nightly_workflow]:
            for job_name, job in workflow.get("jobs", {}).items():
                steps = job.get("steps", [])
                checkout_steps = [s for s in steps if "checkout" in s.get("uses", "").lower()]
                assert len(checkout_steps) >= 1, f"Job {job_name} missing checkout"

    def test_all_have_permissions(self, stable_release_workflow, nightly_workflow):
        """Verify all workflows define permissions."""
        for workflow in [stable_release_workflow, nightly_workflow]:
            assert "permissions" in workflow

    def test_all_have_contents_write(self, stable_release_workflow, nightly_workflow):
        """Verify all release workflows have contents:write permission."""
        for workflow in [stable_release_workflow, nightly_workflow]:
            permissions = workflow.get("permissions", {})
            assert permissions.get("contents") == "write"

    def test_all_use_github_token(self, stable_release_workflow, nightly_workflow):
        """Verify all workflows use GITHUB_TOKEN for releases."""
        for workflow in [stable_release_workflow, nightly_workflow]:
            workflow_str = str(workflow)
            assert "GITHUB_TOKEN" in workflow_str or "GH_TOKEN" in workflow_str

    def test_stable_and_nightly_target_different_branches(
        self, stable_release_workflow, nightly_workflow
    ):
        """Verify stable targets main and nightly targets dev."""
        stable_triggers = _get_triggers(stable_release_workflow)
        assert "main" in stable_triggers.get("workflow_run", {}).get("branches", [])

        nightly_prepare = nightly_workflow["jobs"]["prepare"]
        checkout = next(
            (s for s in nightly_prepare["steps"] if "checkout" in s.get("uses", "").lower()), None
        )
        assert checkout.get("with", {}).get("ref") == "dev"
