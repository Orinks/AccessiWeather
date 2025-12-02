"""
Tests for Briefcase Build workflow configuration.

These tests validate the GitHub Actions workflow for building and packaging
AccessiWeather using Briefcase. They verify YAML structure, build matrix
configuration, job dependencies, and environment settings.

Marked with 'ci' marker to separate from main application tests.
Run with: pytest tests/ci/ -v
"""

from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.ci


@pytest.fixture
def workflow_path():
    return Path(__file__).parent.parent.parent / ".github" / "workflows" / "briefcase-build.yml"


@pytest.fixture
def build_workflow(workflow_path):
    with open(workflow_path) as f:
        return yaml.safe_load(f)


class TestBuildWorkflowStructure:
    """Tests for the workflow file structure and naming."""

    def test_workflow_file_exists(self, workflow_path):
        """Verify the workflow file exists."""
        assert workflow_path.exists(), f"Workflow file not found at {workflow_path}"

    def test_workflow_name(self, build_workflow):
        """Verify the workflow has the expected name."""
        assert build_workflow["name"] == "Build and Package with Briefcase"

    def test_workflow_triggers(self, build_workflow):
        """Verify workflow triggers include workflow_dispatch and workflow_run."""
        triggers = build_workflow[True]
        assert "workflow_dispatch" in triggers, "workflow_dispatch trigger missing"
        assert "workflow_run" in triggers, "workflow_run trigger missing"

    def test_workflow_dispatch_has_inputs(self, build_workflow):
        """Verify workflow_dispatch has expected inputs."""
        inputs = build_workflow[True]["workflow_dispatch"]["inputs"]
        assert "version_override" in inputs
        assert "skip_cache" in inputs
        assert "force_rebuild" in inputs

    def test_workflow_run_triggers_on_ci_completion(self, build_workflow):
        """Verify workflow_run triggers after CI workflow completes."""
        workflow_run = build_workflow[True]["workflow_run"]
        assert workflow_run["workflows"] == ["CI"]
        assert workflow_run["types"] == ["completed"]

    def test_workflow_run_branches(self, build_workflow):
        """Verify workflow_run triggers on expected branches."""
        branches = build_workflow[True]["workflow_run"]["branches"]
        assert "main" in branches
        assert "dev" in branches

    def test_default_shell_is_bash(self, build_workflow):
        """Verify default shell is bash for cross-platform consistency."""
        assert build_workflow["defaults"]["run"]["shell"] == "bash"

    def test_concurrency_configured(self, build_workflow):
        """Verify concurrency is configured to cancel in-progress builds."""
        assert "concurrency" in build_workflow
        concurrency = build_workflow["concurrency"]
        assert "group" in concurrency
        assert "cancel-in-progress" in concurrency

    def test_permissions_defined(self, build_workflow):
        """Verify required permissions are defined."""
        permissions = build_workflow["permissions"]
        assert permissions["contents"] == "read"
        assert permissions["actions"] == "write"


class TestBuildMatrix:
    """Tests for the build matrix configuration."""

    def test_windows_in_matrix(self, build_workflow):
        """Verify Windows is included in the build matrix."""
        matrix = build_workflow["jobs"]["build"]["strategy"]["matrix"]["include"]
        windows_entry = next((m for m in matrix if m["platform"] == "windows"), None)
        assert windows_entry is not None, "Windows not found in build matrix"
        assert windows_entry["os"] == "windows-latest"

    def test_macos_in_matrix(self, build_workflow):
        """Verify macOS is included in the build matrix."""
        matrix = build_workflow["jobs"]["build"]["strategy"]["matrix"]["include"]
        macos_entry = next((m for m in matrix if m["platform"] == "macOS"), None)
        assert macos_entry is not None, "macOS not found in build matrix"
        assert macos_entry["os"] == "macos-latest"

    def test_installer_patterns_defined(self, build_workflow):
        """Verify installer patterns are defined for each platform."""
        matrix = build_workflow["jobs"]["build"]["strategy"]["matrix"]["include"]
        windows_entry = next((m for m in matrix if m["platform"] == "windows"), None)
        macos_entry = next((m for m in matrix if m["platform"] == "macOS"), None)

        assert windows_entry["installer_pattern"] == "*.msi"
        assert macos_entry["installer_pattern"] == "*.dmg"

    def test_matrix_fail_fast_disabled(self, build_workflow):
        """Verify fail-fast is disabled so all platforms build even if one fails."""
        strategy = build_workflow["jobs"]["build"]["strategy"]
        assert strategy["fail-fast"] is False

    def test_matrix_has_two_platforms(self, build_workflow):
        """Verify exactly two platforms are in the build matrix."""
        matrix = build_workflow["jobs"]["build"]["strategy"]["matrix"]["include"]
        assert len(matrix) == 2, f"Expected 2 platforms, got {len(matrix)}"


class TestCheckReleaseJob:
    """Tests for the check-release job configuration."""

    def test_check_release_job_exists(self, build_workflow):
        """Verify check-release job exists."""
        assert "check-release" in build_workflow["jobs"]

    def test_check_release_runs_on_ubuntu(self, build_workflow):
        """Verify check-release runs on ubuntu-latest."""
        job = build_workflow["jobs"]["check-release"]
        assert job["runs-on"] == "ubuntu-latest"

    def test_check_release_outputs_should_build(self, build_workflow):
        """Verify check-release job outputs should_build."""
        job = build_workflow["jobs"]["check-release"]
        assert "outputs" in job
        assert "should_build" in job["outputs"]

    def test_check_release_output_references_step(self, build_workflow):
        """Verify should_build output references the check step."""
        job = build_workflow["jobs"]["check-release"]
        output = job["outputs"]["should_build"]
        assert "steps.check.outputs.should_build" in output

    def test_check_release_has_checkout_step(self, build_workflow):
        """Verify check-release job checks out code."""
        job = build_workflow["jobs"]["check-release"]
        step_names = [s.get("name", "") for s in job["steps"]]
        assert any("checkout" in name.lower() for name in step_names)

    def test_check_release_uses_github_token(self, build_workflow):
        """Verify check-release job uses GITHUB_TOKEN for API calls."""
        job = build_workflow["jobs"]["check-release"]
        check_step = next((s for s in job["steps"] if s.get("id") == "check"), None)
        assert check_step is not None
        assert "GH_TOKEN" in check_step.get("env", {})


class TestBuildJob:
    """Tests for the build job configuration."""

    def test_build_job_exists(self, build_workflow):
        """Verify build job exists."""
        assert "build" in build_workflow["jobs"]

    def test_build_depends_on_check_release(self, build_workflow):
        """Verify build job depends on check-release."""
        job = build_workflow["jobs"]["build"]
        assert "check-release" in job["needs"]

    def test_build_job_condition(self, build_workflow):
        """Verify build job has correct conditional logic."""
        job = build_workflow["jobs"]["build"]
        condition = job["if"]
        assert "workflow_dispatch" in condition
        assert "workflow_run" in condition
        assert "needs.check-release.outputs.should_build" in condition

    def test_build_outputs_version(self, build_workflow):
        """Verify build job outputs version."""
        job = build_workflow["jobs"]["build"]
        assert "outputs" in job
        assert "version" in job["outputs"]

    def test_version_extraction_step_exists(self, build_workflow):
        """Verify version extraction step exists."""
        job = build_workflow["jobs"]["build"]
        step = next((s for s in job["steps"] if s.get("id") == "version"), None)
        assert step is not None, "Version extraction step not found"
        assert step["name"] == "Extract version"

    def test_version_extraction_uses_pyproject(self, build_workflow):
        """Verify version extraction reads from pyproject.toml."""
        job = build_workflow["jobs"]["build"]
        step = next((s for s in job["steps"] if s.get("id") == "version"), None)
        assert "pyproject.toml" in step["run"]
        assert "tomllib" in step["run"]

    def test_version_extraction_supports_override(self, build_workflow):
        """Verify version extraction supports version_override input."""
        job = build_workflow["jobs"]["build"]
        step = next((s for s in job["steps"] if s.get("id") == "version"), None)
        assert "version_override" in step["run"]

    def test_artifact_upload_configured(self, build_workflow):
        """Verify artifact upload steps exist."""
        job = build_workflow["jobs"]["build"]
        upload_steps = [s for s in job["steps"] if "upload-artifact" in str(s.get("uses", ""))]
        assert len(upload_steps) >= 2, "Expected at least 2 artifact upload steps"

    def test_installer_artifact_upload(self, build_workflow):
        """Verify installer artifact upload is configured correctly."""
        job = build_workflow["jobs"]["build"]
        upload_step = next(
            (s for s in job["steps"] if s.get("name") == "Upload Installer artifact"),
            None,
        )
        assert upload_step is not None
        assert upload_step["uses"].startswith("actions/upload-artifact@")
        assert "installer_pattern" in str(upload_step["with"]["path"])

    def test_portable_artifact_upload_windows_only(self, build_workflow):
        """Verify portable artifact upload is Windows-only."""
        job = build_workflow["jobs"]["build"]
        upload_step = next(
            (s for s in job["steps"] if "portable" in s.get("name", "").lower()),
            None,
        )
        assert upload_step is not None
        assert upload_step["if"] == "matrix.platform == 'windows'"

    def test_build_logs_uploaded_on_failure(self, build_workflow):
        """Verify build logs are uploaded on failure."""
        job = build_workflow["jobs"]["build"]
        log_step = next(
            (
                s
                for s in job["steps"]
                if "logs" in s.get("name", "").lower() and "failure" in s.get("name", "").lower()
            ),
            None,
        )
        assert log_step is not None
        assert log_step["if"] == "failure()"


class TestCacheConfiguration:
    """Tests for cache configuration in the build job."""

    def test_pip_cache_configured(self, build_workflow):
        """Verify pip dependency cache is configured."""
        job = build_workflow["jobs"]["build"]
        cache_step = next(
            (s for s in job["steps"] if "Cache pip" in s.get("name", "")),
            None,
        )
        assert cache_step is not None
        assert cache_step["uses"].startswith("actions/cache@")
        assert "pip" in cache_step["with"]["path"]

    def test_briefcase_cache_configured(self, build_workflow):
        """Verify Briefcase build cache is configured."""
        job = build_workflow["jobs"]["build"]
        cache_step = next(
            (s for s in job["steps"] if "Cache Briefcase" in s.get("name", "")),
            None,
        )
        assert cache_step is not None
        assert cache_step["uses"].startswith("actions/cache@")

    def test_briefcase_cache_includes_build_directories(self, build_workflow):
        """Verify Briefcase cache includes build/dist/logs directories."""
        job = build_workflow["jobs"]["build"]
        cache_step = next(
            (s for s in job["steps"] if "Cache Briefcase" in s.get("name", "")),
            None,
        )
        path = cache_step["with"]["path"]
        assert "build/" in path
        assert "dist/" in path
        assert "logs/" in path

    def test_briefcase_cache_key_uses_source_hash(self, build_workflow):
        """Verify Briefcase cache key uses source file hash."""
        job = build_workflow["jobs"]["build"]
        cache_step = next(
            (s for s in job["steps"] if "Cache Briefcase" in s.get("name", "")),
            None,
        )
        key = cache_step["with"]["key"]
        assert "hashFiles" in key
        assert "pyproject.toml" in key

    def test_briefcase_cache_respects_skip_cache_input(self, build_workflow):
        """Verify Briefcase cache can be skipped via input."""
        job = build_workflow["jobs"]["build"]
        cache_step = next(
            (s for s in job["steps"] if "Cache Briefcase" in s.get("name", "")),
            None,
        )
        assert "skip_cache" in cache_step["if"]


class TestValidateJob:
    """Tests for the validate job configuration."""

    def test_validate_job_exists(self, build_workflow):
        """Verify validate job exists."""
        assert "validate" in build_workflow["jobs"]

    def test_validate_depends_on_build(self, build_workflow):
        """Verify validate job depends on build and check-release."""
        job = build_workflow["jobs"]["validate"]
        needs = job["needs"]
        assert "build" in needs
        assert "check-release" in needs

    def test_validate_runs_on_windows(self, build_workflow):
        """Verify validate job runs on Windows for MSI verification."""
        job = build_workflow["jobs"]["validate"]
        assert job["runs-on"] == "windows-latest"

    def test_validate_downloads_artifacts(self, build_workflow):
        """Verify validate job downloads build artifacts."""
        job = build_workflow["jobs"]["validate"]
        download_steps = [s for s in job["steps"] if "download-artifact" in str(s.get("uses", ""))]
        assert len(download_steps) >= 2, "Expected at least 2 artifact download steps"

    def test_validate_checks_installer_artifact(self, build_workflow):
        """Verify validate job downloads installer artifact."""
        job = build_workflow["jobs"]["validate"]
        download_step = next(
            (s for s in job["steps"] if "installer" in s.get("name", "").lower()),
            None,
        )
        assert download_step is not None
        assert "windows-installer" in download_step["with"]["name"]

    def test_validate_checks_portable_artifact(self, build_workflow):
        """Verify validate job downloads portable artifact."""
        job = build_workflow["jobs"]["validate"]
        download_step = next(
            (s for s in job["steps"] if "portable" in s.get("name", "").lower()),
            None,
        )
        assert download_step is not None
        assert "windows-portable" in download_step["with"]["name"]

    def test_validate_has_condition(self, build_workflow):
        """Verify validate job runs only when should_build is true."""
        job = build_workflow["jobs"]["validate"]
        assert "should_build" in job["if"]


class TestEnvironmentVariables:
    """Tests for environment variable configuration."""

    def test_force_color_disabled(self, build_workflow):
        """Verify FORCE_COLOR is set to 0 to prevent encoding issues on Windows."""
        env = build_workflow["env"]
        assert env["FORCE_COLOR"] == "0", "FORCE_COLOR should be '0' to prevent encoding issues"

    def test_pythonutf8_enabled(self, build_workflow):
        """Verify PYTHONUTF8 is enabled for consistent encoding."""
        env = build_workflow["env"]
        assert env["PYTHONUTF8"] == "1", "PYTHONUTF8 should be '1' for UTF-8 encoding"

    def test_python_version_defined(self, build_workflow):
        """Verify Python version is defined in environment."""
        env = build_workflow["env"]
        assert "PYTHON_VERSION" in env
        assert env["PYTHON_VERSION"] == "3.12"


class TestBuildSteps:
    """Tests for individual build steps in the build job."""

    def test_checkout_step_exists(self, build_workflow):
        """Verify checkout step exists with full history."""
        job = build_workflow["jobs"]["build"]
        checkout_step = next(
            (s for s in job["steps"] if "checkout" in s.get("name", "").lower()),
            None,
        )
        assert checkout_step is not None
        assert checkout_step["with"]["fetch-depth"] == 0

    def test_setup_python_step_exists(self, build_workflow):
        """Verify Python setup step exists."""
        job = build_workflow["jobs"]["build"]
        python_step = next(
            (s for s in job["steps"] if "Set up Python" in s.get("name", "")),
            None,
        )
        assert python_step is not None
        assert python_step["uses"].startswith("actions/setup-python@")

    def test_briefcase_create_step_exists(self, build_workflow):
        """Verify Briefcase create step exists."""
        job = build_workflow["jobs"]["build"]
        create_step = next(
            (s for s in job["steps"] if "Create Briefcase" in s.get("name", "")),
            None,
        )
        assert create_step is not None
        assert "installer/make.py create" in create_step["run"]

    def test_briefcase_build_step_exists(self, build_workflow):
        """Verify Briefcase build step exists."""
        job = build_workflow["jobs"]["build"]
        build_step = next(
            (s for s in job["steps"] if s.get("name") == "Build Briefcase app"),
            None,
        )
        assert build_step is not None
        assert "installer/make.py build" in build_step["run"]

    def test_briefcase_package_step_exists(self, build_workflow):
        """Verify Briefcase package step exists."""
        job = build_workflow["jobs"]["build"]
        package_step = next(
            (s for s in job["steps"] if "Package Briefcase" in s.get("name", "")),
            None,
        )
        assert package_step is not None
        assert "installer/make.py package" in package_step["run"]

    def test_portable_zip_step_windows_only(self, build_workflow):
        """Verify portable ZIP creation is Windows-only."""
        job = build_workflow["jobs"]["build"]
        zip_step = next(
            (s for s in job["steps"] if "portable zip" in s.get("name", "").lower()),
            None,
        )
        assert zip_step is not None
        assert zip_step["if"] == "matrix.platform == 'windows'"

    def test_verify_build_outputs_step_exists(self, build_workflow):
        """Verify build outputs verification step exists."""
        job = build_workflow["jobs"]["build"]
        verify_step = next(
            (s for s in job["steps"] if "Verify build outputs" in s.get("name", "")),
            None,
        )
        assert verify_step is not None

    def test_verify_step_generates_checksums(self, build_workflow):
        """Verify the verify step generates checksums."""
        job = build_workflow["jobs"]["build"]
        verify_step = next(
            (s for s in job["steps"] if "Verify build outputs" in s.get("name", "")),
            None,
        )
        assert "checksums.txt" in verify_step["run"]
        assert "SHA256" in verify_step["run"]


class TestArtifactRetention:
    """Tests for artifact retention configuration."""

    def test_installer_artifact_retention(self, build_workflow):
        """Verify installer artifact has appropriate retention."""
        job = build_workflow["jobs"]["build"]
        upload_step = next(
            (s for s in job["steps"] if s.get("name") == "Upload Installer artifact"),
            None,
        )
        assert upload_step["with"]["retention-days"] == 90

    def test_portable_artifact_retention(self, build_workflow):
        """Verify portable artifact has appropriate retention."""
        job = build_workflow["jobs"]["build"]
        upload_step = next(
            (
                s
                for s in job["steps"]
                if "portable" in s.get("name", "").lower() and "upload" in s.get("name", "").lower()
            ),
            None,
        )
        assert upload_step["with"]["retention-days"] == 30


class TestJobOrder:
    """Tests for job execution order and dependencies."""

    def test_all_expected_jobs_exist(self, build_workflow):
        """Verify all expected jobs are defined."""
        jobs = build_workflow["jobs"]
        assert "check-release" in jobs
        assert "build" in jobs
        assert "validate" in jobs

    def test_job_dependency_chain(self, build_workflow):
        """Verify correct job dependency chain: check-release -> build -> validate."""
        jobs = build_workflow["jobs"]
        assert "check-release" in jobs["build"]["needs"]
        needs = jobs["validate"]["needs"]
        assert "build" in needs
        assert "check-release" in needs
