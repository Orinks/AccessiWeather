"""
Tests for CI workflow configuration.

Validates the CI workflow YAML structure, job dependencies,
and configuration settings.

Marked with 'ci' marker to separate from main application tests.
Run with: pytest tests/ci/ -v
"""

from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.ci


@pytest.fixture
def ci_workflow():
    workflow_path = Path(__file__).parent.parent.parent / ".github" / "workflows" / "ci.yml"
    with open(workflow_path) as f:
        return yaml.safe_load(f)


@pytest.fixture
def lint_job(ci_workflow):
    return ci_workflow["jobs"]["lint"]


@pytest.fixture
def tests_job(ci_workflow):
    return ci_workflow["jobs"]["tests"]


class TestCIWorkflowStructure:
    """Tests for basic CI workflow structure."""

    def test_workflow_has_name(self, ci_workflow):
        """Verify workflow has the correct name."""
        assert ci_workflow.get("name") == "CI"

    def test_workflow_triggers_on_push(self, ci_workflow):
        """Verify workflow triggers on push to main and dev branches."""
        triggers = ci_workflow[True]
        assert "push" in triggers
        push_config = triggers["push"]
        assert "branches" in push_config
        assert "main" in push_config["branches"]
        assert "dev" in push_config["branches"]

    def test_workflow_triggers_on_pull_request(self, ci_workflow):
        """Verify workflow triggers on pull requests to main and dev branches."""
        triggers = ci_workflow[True]
        assert "pull_request" in triggers
        pr_config = triggers["pull_request"]
        assert "branches" in pr_config
        assert "main" in pr_config["branches"]
        assert "dev" in pr_config["branches"]

    def test_workflow_triggers_on_manual_dispatch(self, ci_workflow):
        """Verify workflow can be triggered manually."""
        triggers = ci_workflow[True]
        assert "workflow_dispatch" in triggers

    def test_lint_job_exists(self, ci_workflow):
        """Verify lint job is defined."""
        assert "lint" in ci_workflow["jobs"]

    def test_tests_job_exists(self, ci_workflow):
        """Verify tests job is defined."""
        assert "tests" in ci_workflow["jobs"]

    def test_default_shell_is_bash(self, ci_workflow):
        """Verify default shell is set to bash."""
        assert "defaults" in ci_workflow
        assert ci_workflow["defaults"]["run"]["shell"] == "bash"


class TestJobDependencies:
    """Tests for job dependency configuration."""

    def test_tests_depends_on_lint(self, tests_job):
        """Verify tests job depends on lint job."""
        assert "needs" in tests_job
        assert tests_job["needs"] == "lint"

    def test_lint_has_no_dependencies(self, lint_job):
        """Verify lint job has no dependencies (runs first)."""
        assert "needs" not in lint_job


class TestPythonMatrix:
    """Tests for Python version matrix configuration."""

    def test_python_versions_valid(self, tests_job):
        """Verify Python 3.11 and 3.12 are tested."""
        strategy = tests_job["strategy"]
        matrix = strategy["matrix"]
        python_versions = matrix["python-version"]
        assert "3.11" in python_versions
        assert "3.12" in python_versions
        assert len(python_versions) == 2

    def test_matrix_fail_fast_disabled(self, tests_job):
        """Verify fail-fast is disabled to run all matrix combinations."""
        strategy = tests_job["strategy"]
        assert strategy.get("fail-fast") is False

    def test_lint_uses_python_312(self, lint_job):
        """Verify lint job uses Python 3.12."""
        setup_python_step = None
        for step in lint_job["steps"]:
            if step.get("name") == "Set up Python":
                setup_python_step = step
                break
        assert setup_python_step is not None
        assert setup_python_step["with"]["python-version"] == "3.12"


class TestEnvironmentVariables:
    """Tests for environment variable configuration."""

    def test_force_color_set_globally(self, ci_workflow):
        """Verify FORCE_COLOR is set globally to prevent encoding issues."""
        assert "env" in ci_workflow
        assert ci_workflow["env"]["FORCE_COLOR"] == "1"

    def test_tests_job_sets_pythonpath(self, tests_job):
        """Verify PYTHONPATH is set for test execution."""
        run_tests_step = None
        for step in tests_job["steps"]:
            if step.get("name") == "Run tests":
                run_tests_step = step
                break
        assert run_tests_step is not None
        assert run_tests_step["env"]["PYTHONPATH"] == "src"

    def test_tests_job_sets_test_mode(self, tests_job):
        """Verify ACCESSIWEATHER_TEST_MODE is set for test execution."""
        run_tests_step = None
        for step in tests_job["steps"]:
            if step.get("name") == "Run tests":
                run_tests_step = step
                break
        assert run_tests_step is not None
        assert run_tests_step["env"]["ACCESSIWEATHER_TEST_MODE"] == "1"


class TestConcurrency:
    """Tests for concurrency configuration."""

    def test_concurrency_group_uses_workflow_and_ref(self, ci_workflow):
        """Verify concurrency group includes workflow name and ref."""
        assert "concurrency" in ci_workflow
        group = ci_workflow["concurrency"]["group"]
        assert "${{ github.workflow }}" in group
        assert "${{ github.ref }}" in group

    def test_cancel_in_progress_for_prs(self, ci_workflow):
        """Verify cancel-in-progress is enabled for pull requests only."""
        concurrency = ci_workflow["concurrency"]
        cancel_in_progress = concurrency["cancel-in-progress"]
        assert "${{ github.event_name == 'pull_request' }}" in cancel_in_progress


class TestTestCommand:
    """Tests for pytest command configuration."""

    def test_pytest_uses_parallel_execution(self, tests_job):
        """Verify pytest uses -n auto for parallel execution."""
        run_tests_step = None
        for step in tests_job["steps"]:
            if step.get("name") == "Run tests":
                run_tests_step = step
                break
        assert run_tests_step is not None
        run_command = run_tests_step["run"]
        assert "-n auto" in run_command

    def test_integration_tests_excluded(self, tests_job):
        """Verify integration tests are excluded from CI run."""
        run_tests_step = None
        for step in tests_job["steps"]:
            if step.get("name") == "Run tests":
                run_tests_step = step
                break
        assert run_tests_step is not None
        run_command = run_tests_step["run"]
        assert '-m "not integration"' in run_command

    def test_verbose_output_enabled(self, tests_job):
        """Verify verbose output is enabled for test debugging."""
        run_tests_step = None
        for step in tests_job["steps"]:
            if step.get("name") == "Run tests":
                run_tests_step = step
                break
        assert run_tests_step is not None
        run_command = run_tests_step["run"]
        assert "-v" in run_command

    def test_junit_xml_report_generated(self, tests_job):
        """Verify JUnit XML report is generated for CI integration."""
        run_tests_step = None
        for step in tests_job["steps"]:
            if step.get("name") == "Run tests":
                run_tests_step = step
                break
        assert run_tests_step is not None
        run_command = run_tests_step["run"]
        assert "--junitxml=reports/junit.xml" in run_command


class TestArtifactUpload:
    """Tests for artifact upload configuration."""

    def test_upload_artifact_step_exists(self, tests_job):
        """Verify upload artifact step is defined."""
        upload_step = None
        for step in tests_job["steps"]:
            if step.get("name") == "Upload test report":
                upload_step = step
                break
        assert upload_step is not None

    def test_upload_artifact_uses_correct_action(self, tests_job):
        """Verify correct GitHub action version is used for upload."""
        upload_step = None
        for step in tests_job["steps"]:
            if step.get("name") == "Upload test report":
                upload_step = step
                break
        assert upload_step is not None
        assert upload_step["uses"] == "actions/upload-artifact@v5"

    def test_upload_artifact_runs_always(self, tests_job):
        """Verify artifact upload runs even on failure."""
        upload_step = None
        for step in tests_job["steps"]:
            if step.get("name") == "Upload test report":
                upload_step = step
                break
        assert upload_step is not None
        assert upload_step["if"] == "always()"

    def test_artifact_name_includes_python_version(self, tests_job):
        """Verify artifact name includes Python version for distinction."""
        upload_step = None
        for step in tests_job["steps"]:
            if step.get("name") == "Upload test report":
                upload_step = step
                break
        assert upload_step is not None
        artifact_name = upload_step["with"]["name"]
        assert "${{ matrix.python-version }}" in artifact_name

    def test_artifact_retention_days_set(self, tests_job):
        """Verify artifact retention period is configured."""
        upload_step = None
        for step in tests_job["steps"]:
            if step.get("name") == "Upload test report":
                upload_step = step
                break
        assert upload_step is not None
        assert upload_step["with"]["retention-days"] == 7


class TestJobConfiguration:
    """Tests for job-level configuration."""

    def test_lint_runs_on_ubuntu_latest(self, lint_job):
        """Verify lint job runs on ubuntu-latest."""
        assert lint_job["runs-on"] == "ubuntu-latest"

    def test_tests_runs_on_ubuntu_latest(self, tests_job):
        """Verify tests job runs on ubuntu-latest."""
        assert tests_job["runs-on"] == "ubuntu-latest"

    def test_lint_job_has_name(self, lint_job):
        """Verify lint job has a descriptive name."""
        assert lint_job["name"] == "Lint"

    def test_tests_job_has_dynamic_name(self, tests_job):
        """Verify tests job name includes Python version."""
        job_name = tests_job["name"]
        assert "${{ matrix.python-version }}" in job_name


class TestCheckoutStep:
    """Tests for checkout step configuration."""

    def test_lint_uses_checkout_v6(self, lint_job):
        """Verify lint job uses checkout action v6."""
        checkout_step = lint_job["steps"][0]
        assert checkout_step["uses"] == "actions/checkout@v6"

    def test_tests_uses_checkout_v6(self, tests_job):
        """Verify tests job uses checkout action v6."""
        checkout_step = tests_job["steps"][0]
        assert checkout_step["uses"] == "actions/checkout@v6"


class TestSetupPythonStep:
    """Tests for Python setup step configuration."""

    def test_lint_uses_setup_python_v6(self, lint_job):
        """Verify lint job uses setup-python action v6."""
        setup_step = None
        for step in lint_job["steps"]:
            if step.get("name") == "Set up Python":
                setup_step = step
                break
        assert setup_step is not None
        assert setup_step["uses"] == "actions/setup-python@v6"

    def test_tests_uses_setup_python_v6(self, tests_job):
        """Verify tests job uses setup-python action v6."""
        setup_step = None
        for step in tests_job["steps"]:
            if step.get("name") == "Set up Python":
                setup_step = step
                break
        assert setup_step is not None
        assert setup_step["uses"] == "actions/setup-python@v6"

    def test_pip_cache_enabled(self, lint_job):
        """Verify pip cache is enabled for faster builds."""
        setup_step = None
        for step in lint_job["steps"]:
            if step.get("name") == "Set up Python":
                setup_step = step
                break
        assert setup_step is not None
        assert setup_step["with"].get("cache") == "pip"


class TestSystemDependencies:
    """Tests for system dependency installation."""

    def test_lint_installs_system_deps(self, lint_job):
        """Verify lint job installs required system dependencies."""
        install_step = None
        for step in lint_job["steps"]:
            if step.get("name") == "Install system dependencies":
                install_step = step
                break
        assert install_step is not None
        run_command = install_step["run"]
        assert "libcairo2-dev" in run_command
        assert "libgirepository-2.0-dev" in run_command

    def test_tests_installs_system_deps(self, tests_job):
        """Verify tests job installs required system dependencies."""
        install_step = None
        for step in tests_job["steps"]:
            if step.get("name") == "Install system dependencies":
                install_step = step
                break
        assert install_step is not None
        run_command = install_step["run"]
        assert "libcairo2-dev" in run_command
        assert "libgirepository-2.0-dev" in run_command


class TestLintSteps:
    """Tests for lint-specific steps."""

    def test_ruff_format_step_exists(self, lint_job):
        """Verify ruff format step is defined."""
        ruff_format_step = None
        for step in lint_job["steps"]:
            if step.get("name") == "Ruff format":
                ruff_format_step = step
                break
        assert ruff_format_step is not None
        assert "ruff format" in ruff_format_step["run"]

    def test_ruff_lint_step_exists(self, lint_job):
        """Verify ruff lint step is defined."""
        ruff_lint_step = None
        for step in lint_job["steps"]:
            if step.get("name") == "Ruff lint":
                ruff_lint_step = step
                break
        assert ruff_lint_step is not None
        assert "ruff check" in ruff_lint_step["run"]

    def test_briefcase_build_step_exists(self, lint_job):
        """Verify briefcase build step is defined for headless build validation."""
        build_step = None
        for step in lint_job["steps"]:
            if step.get("name") == "Build and package (headless)":
                build_step = step
                break
        assert build_step is not None
        assert "installer/make.py" in build_step["run"]


class TestCISummaryStep:
    """Tests for CI summary step configuration."""

    def test_ci_summary_step_exists(self, tests_job):
        """Verify CI summary step is defined."""
        summary_step = None
        for step in tests_job["steps"]:
            if step.get("name") == "CI Summary":
                summary_step = step
                break
        assert summary_step is not None

    def test_ci_summary_runs_always(self, tests_job):
        """Verify CI summary runs even on failure."""
        summary_step = None
        for step in tests_job["steps"]:
            if step.get("name") == "CI Summary":
                summary_step = step
                break
        assert summary_step is not None
        assert summary_step["if"] == "always()"

    def test_ci_summary_includes_branch_info(self, tests_job):
        """Verify CI summary outputs branch information."""
        summary_step = None
        for step in tests_job["steps"]:
            if step.get("name") == "CI Summary":
                summary_step = step
                break
        assert summary_step is not None
        run_command = summary_step["run"]
        assert "${{ github.ref_name }}" in run_command

    def test_ci_summary_includes_commit_info(self, tests_job):
        """Verify CI summary outputs commit information."""
        summary_step = None
        for step in tests_job["steps"]:
            if step.get("name") == "CI Summary":
                summary_step = step
                break
        assert summary_step is not None
        run_command = summary_step["run"]
        assert "${{ github.sha }}" in run_command
