"""Tests for integration tests workflow configuration."""

from pathlib import Path

import pytest
import yaml


@pytest.fixture
def integration_workflow():
    """Load the integration tests workflow configuration."""
    path = Path(__file__).parent.parent.parent / ".github" / "workflows" / "integration-tests.yml"
    with open(path) as f:
        return yaml.safe_load(f)


@pytest.mark.ci
class TestIntegrationWorkflowStructure:
    """Tests for basic workflow structure."""

    def test_workflow_name(self, integration_workflow):
        """Verify workflow has correct name."""
        assert integration_workflow["name"] == "Integration Tests"

    def test_schedule_trigger(self, integration_workflow):
        """Verify schedule trigger runs at 6 AM UTC daily."""
        triggers = integration_workflow[True]
        assert "schedule" in triggers
        schedules = triggers["schedule"]
        assert len(schedules) == 1
        assert schedules[0]["cron"] == "0 6 * * *"

    def test_schedule_cron_format_valid(self, integration_workflow):
        """Verify cron format has 5 fields."""
        cron = integration_workflow[True]["schedule"][0]["cron"]
        fields = cron.split()
        assert len(fields) == 5, "Cron should have 5 fields: minute hour day month weekday"

    def test_manual_dispatch_enabled(self, integration_workflow):
        """Verify workflow_dispatch is enabled for manual runs."""
        triggers = integration_workflow[True]
        assert "workflow_dispatch" in triggers


@pytest.mark.ci
class TestJobConfiguration:
    """Tests for job configuration."""

    def test_job_exists(self, integration_workflow):
        """Verify integration-tests job exists."""
        assert "integration-tests" in integration_workflow["jobs"]

    def test_conditional_only_schedule_or_dispatch(self, integration_workflow):
        """Verify job only runs on schedule or manual dispatch."""
        job = integration_workflow["jobs"]["integration-tests"]
        assert "if" in job
        condition = job["if"]
        assert "schedule" in condition
        assert "workflow_dispatch" in condition

    def test_runs_on_ubuntu(self, integration_workflow):
        """Verify job runs on ubuntu-latest."""
        job = integration_workflow["jobs"]["integration-tests"]
        assert job["runs-on"] == "ubuntu-latest"

    def test_python_version(self, integration_workflow):
        """Verify correct Python version is used."""
        job = integration_workflow["jobs"]["integration-tests"]
        python_versions = job["strategy"]["matrix"]["python-version"]
        assert "3.12" in python_versions

    def test_fail_fast_disabled(self, integration_workflow):
        """Verify fail-fast is disabled for matrix."""
        job = integration_workflow["jobs"]["integration-tests"]
        assert job["strategy"]["fail-fast"] is False

    def test_job_name(self, integration_workflow):
        """Verify job has descriptive name."""
        job = integration_workflow["jobs"]["integration-tests"]
        assert job["name"] == "Weather Provider Integration Tests"


@pytest.mark.ci
class TestTestExecution:
    """Tests for test execution configuration."""

    def test_runs_integration_tests(self, integration_workflow):
        """Verify integration tests are run with pytest."""
        job = integration_workflow["jobs"]["integration-tests"]
        steps = job["steps"]
        test_step = next((s for s in steps if s.get("name") == "Run integration tests"), None)
        assert test_step is not None
        assert "pytest tests/integration/" in test_step["run"]

    def test_integration_env_var_set(self, integration_workflow):
        """Verify RUN_INTEGRATION_TESTS env var is set."""
        job = integration_workflow["jobs"]["integration-tests"]
        steps = job["steps"]
        test_step = next((s for s in steps if s.get("name") == "Run integration tests"), None)
        assert test_step is not None
        assert "env" in test_step
        assert test_step["env"]["RUN_INTEGRATION_TESTS"] == "1"

    def test_timeout_set(self, integration_workflow):
        """Verify timeout is set for test step."""
        job = integration_workflow["jobs"]["integration-tests"]
        steps = job["steps"]
        test_step = next((s for s in steps if s.get("name") == "Run integration tests"), None)
        assert test_step is not None
        assert "timeout-minutes" in test_step
        assert test_step["timeout-minutes"] == 15

    def test_verbose_output_enabled(self, integration_workflow):
        """Verify verbose output is enabled for tests."""
        job = integration_workflow["jobs"]["integration-tests"]
        steps = job["steps"]
        test_step = next((s for s in steps if s.get("name") == "Run integration tests"), None)
        assert test_step is not None
        assert "-v" in test_step["run"]


@pytest.mark.ci
class TestIssueManagement:
    """Tests for issue creation and closing on failure/success."""

    def test_failure_notification_step_exists(self, integration_workflow):
        """Verify step exists to notify on failure."""
        job = integration_workflow["jobs"]["integration-tests"]
        steps = job["steps"]
        failure_step = next(
            (
                s
                for s in steps
                if "failure" in s.get("name", "").lower() and "notify" in s.get("name", "").lower()
            ),
            None,
        )
        assert failure_step is not None

    def test_failure_step_condition(self, integration_workflow):
        """Verify failure notification only runs on schedule failures."""
        job = integration_workflow["jobs"]["integration-tests"]
        steps = job["steps"]
        failure_step = next(
            (
                s
                for s in steps
                if "failure" in s.get("name", "").lower() and "notify" in s.get("name", "").lower()
            ),
            None,
        )
        assert failure_step is not None
        assert "failure()" in failure_step["if"]
        assert "schedule" in failure_step["if"]

    def test_failure_step_uses_github_script(self, integration_workflow):
        """Verify failure step uses github-script action."""
        job = integration_workflow["jobs"]["integration-tests"]
        steps = job["steps"]
        failure_step = next(
            (
                s
                for s in steps
                if "failure" in s.get("name", "").lower() and "notify" in s.get("name", "").lower()
            ),
            None,
        )
        assert failure_step is not None
        assert "actions/github-script" in failure_step["uses"]

    def test_success_closes_issues(self, integration_workflow):
        """Verify step exists to close issues on success."""
        job = integration_workflow["jobs"]["integration-tests"]
        steps = job["steps"]
        success_step = next(
            (
                s
                for s in steps
                if "success" in s.get("name", "").lower() and "close" in s.get("name", "").lower()
            ),
            None,
        )
        assert success_step is not None

    def test_success_step_condition(self, integration_workflow):
        """Verify success step only runs on schedule success."""
        job = integration_workflow["jobs"]["integration-tests"]
        steps = job["steps"]
        success_step = next(
            (
                s
                for s in steps
                if "success" in s.get("name", "").lower() and "close" in s.get("name", "").lower()
            ),
            None,
        )
        assert success_step is not None
        assert "success()" in success_step["if"]
        assert "schedule" in success_step["if"]

    def test_success_step_uses_github_script(self, integration_workflow):
        """Verify success step uses github-script action."""
        job = integration_workflow["jobs"]["integration-tests"]
        steps = job["steps"]
        success_step = next(
            (
                s
                for s in steps
                if "success" in s.get("name", "").lower() and "close" in s.get("name", "").lower()
            ),
            None,
        )
        assert success_step is not None
        assert "actions/github-script" in success_step["uses"]

    def test_failure_creates_labeled_issue(self, integration_workflow):
        """Verify failure step creates issue with proper labels."""
        job = integration_workflow["jobs"]["integration-tests"]
        steps = job["steps"]
        failure_step = next(
            (
                s
                for s in steps
                if "failure" in s.get("name", "").lower() and "notify" in s.get("name", "").lower()
            ),
            None,
        )
        assert failure_step is not None
        script = failure_step["with"]["script"]
        assert "integration-test-failure" in script
        assert "issues.create" in script

    def test_success_closes_labeled_issues(self, integration_workflow):
        """Verify success step closes issues with integration-test-failure label."""
        job = integration_workflow["jobs"]["integration-tests"]
        steps = job["steps"]
        success_step = next(
            (
                s
                for s in steps
                if "success" in s.get("name", "").lower() and "close" in s.get("name", "").lower()
            ),
            None,
        )
        assert success_step is not None
        script = success_step["with"]["script"]
        assert "integration-test-failure" in script
        assert "state: 'closed'" in script or "'closed'" in script


@pytest.mark.ci
class TestDependencies:
    """Tests for workflow dependencies and setup."""

    def test_checkout_step_exists(self, integration_workflow):
        """Verify checkout step exists."""
        job = integration_workflow["jobs"]["integration-tests"]
        steps = job["steps"]
        checkout_step = next((s for s in steps if "checkout" in s.get("name", "").lower()), None)
        assert checkout_step is not None
        assert "actions/checkout" in checkout_step["uses"]

    def test_python_setup_step_exists(self, integration_workflow):
        """Verify Python setup step exists."""
        job = integration_workflow["jobs"]["integration-tests"]
        steps = job["steps"]
        python_step = next(
            (
                s
                for s in steps
                if "python" in s.get("name", "").lower() and "set up" in s.get("name", "").lower()
            ),
            None,
        )
        assert python_step is not None
        assert "actions/setup-python" in python_step["uses"]

    def test_pip_cache_enabled(self, integration_workflow):
        """Verify pip caching is enabled."""
        job = integration_workflow["jobs"]["integration-tests"]
        steps = job["steps"]
        python_step = next((s for s in steps if "actions/setup-python" in s.get("uses", "")), None)
        assert python_step is not None
        assert python_step["with"]["cache"] == "pip"

    def test_dependencies_installed(self, integration_workflow):
        """Verify dependencies are installed."""
        job = integration_workflow["jobs"]["integration-tests"]
        steps = job["steps"]
        install_step = next((s for s in steps if s.get("name") == "Install dependencies"), None)
        assert install_step is not None
        assert "requirements-dev.txt" in install_step["run"]
        assert "pip install -e ." in install_step["run"]
