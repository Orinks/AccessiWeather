"""
Tests for GitHub Pages workflow structure validation.

These tests verify that the update-pages.yml workflow has the correct structure
for GitHub Pages deployment, including required actions, permissions, and environment.

**Validates: Requirements 1.1-1.4, 5.1-5.5**
"""

from pathlib import Path

import pytest
import yaml


@pytest.fixture
def workflow_content():
    """Load the update-pages.yml workflow file."""
    workflow_path = Path(".github/workflows/update-pages.yml")
    if not workflow_path.exists():
        pytest.skip("Workflow file not found")
    with open(workflow_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


class TestWorkflowActions:
    """Tests for required GitHub Actions in the workflow."""

    def test_has_upload_pages_artifact_action(self, workflow_content):
        """
        Verify workflow contains actions/upload-pages-artifact action.

        **Validates: Requirements 1.2**
        """
        jobs = workflow_content.get("jobs", {})
        found = False
        for _job_name, job_config in jobs.items():
            steps = job_config.get("steps", [])
            for step in steps:
                uses = step.get("uses", "")
                if "actions/upload-pages-artifact" in uses:
                    found = True
                    break
        assert found, "Workflow must contain actions/upload-pages-artifact action"

    def test_has_deploy_pages_action(self, workflow_content):
        """
        Verify workflow contains actions/deploy-pages action.

        **Validates: Requirements 1.3**
        """
        jobs = workflow_content.get("jobs", {})
        found = False
        for _job_name, job_config in jobs.items():
            steps = job_config.get("steps", [])
            for step in steps:
                uses = step.get("uses", "")
                if "actions/deploy-pages" in uses:
                    found = True
                    break
        assert found, "Workflow must contain actions/deploy-pages action"


class TestWorkflowPermissions:
    """Tests for required permissions in the workflow."""

    def test_has_pages_write_permission(self, workflow_content):
        """
        Verify workflow has pages:write permission.

        **Validates: Requirements 1.4**
        """
        permissions = workflow_content.get("permissions", {})
        assert permissions.get("pages") == "write", "Workflow must have pages:write permission"

    def test_has_id_token_write_permission(self, workflow_content):
        """
        Verify workflow has id-token:write permission for OIDC.

        **Validates: Requirements 1.4**
        """
        permissions = workflow_content.get("permissions", {})
        assert permissions.get("id-token") == "write", (
            "Workflow must have id-token:write permission"
        )


class TestWorkflowEnvironment:
    """Tests for GitHub Pages environment configuration."""

    def test_has_github_pages_environment(self, workflow_content):
        """
        Verify workflow has github-pages environment configured.

        **Validates: Requirements 1.3**
        """
        jobs = workflow_content.get("jobs", {})
        found = False
        for _job_name, job_config in jobs.items():
            environment = job_config.get("environment", {})
            if isinstance(environment, dict):
                if environment.get("name") == "github-pages":
                    found = True
                    break
            elif environment == "github-pages":
                found = True
                break
        assert found, "Workflow must have github-pages environment configured"


class TestWorkflowStructure:
    """Tests for workflow job structure."""

    def test_has_two_jobs(self, workflow_content):
        """
        Verify workflow has at least two jobs (build and deploy).

        **Validates: Requirements 1.1, 1.2, 1.3**
        """
        jobs = workflow_content.get("jobs", {})
        assert len(jobs) >= 2, "Workflow must have at least two jobs (build and deploy)"

    def test_deploy_job_depends_on_build(self, workflow_content):
        """
        Verify deploy job has needs dependency on build job.

        **Validates: Requirements 1.3**
        """
        jobs = workflow_content.get("jobs", {})
        # Find the deploy job (contains deploy-pages action)
        deploy_job = None
        build_job_name = None

        for _job_name, job_config in jobs.items():
            steps = job_config.get("steps", [])
            for step in steps:
                uses = step.get("uses", "")
                if "actions/deploy-pages" in uses:
                    deploy_job = job_config
                elif "actions/upload-pages-artifact" in uses:
                    build_job_name = _job_name

        if deploy_job and build_job_name:
            needs = deploy_job.get("needs", [])
            if isinstance(needs, str):
                needs = [needs]
            assert build_job_name in needs, (
                f"Deploy job must depend on build job ({build_job_name})"
            )


class TestWorkflowTriggers:
    """Tests for workflow trigger configuration."""

    def _get_on_config(self, workflow_content):
        """Get the 'on' config, handling YAML's 'on' -> True conversion."""
        # YAML parses 'on' as boolean True, so check both
        return workflow_content.get("on") or workflow_content.get(True, {})

    def test_has_workflow_run_trigger(self, workflow_content):
        """
        Verify workflow has workflow_run trigger for build workflow.

        **Validates: Requirements 5.1**
        """
        on_config = self._get_on_config(workflow_content)
        assert "workflow_run" in on_config, "Workflow must have workflow_run trigger"

    def test_workflow_run_references_briefcase_build(self, workflow_content):
        """
        Verify workflow_run trigger references the correct build workflow.

        **Validates: Requirements 5.1**
        """
        on_config = self._get_on_config(workflow_content)
        workflow_run = on_config.get("workflow_run", {})
        workflows = workflow_run.get("workflows", [])
        assert "Build and Package with Briefcase" in workflows, (
            "workflow_run must reference 'Build and Package with Briefcase' workflow"
        )

    def test_has_concurrency_configuration(self, workflow_content):
        """
        Verify workflow has concurrency configuration.

        **Validates: Requirements 5.5**
        """
        concurrency = workflow_content.get("concurrency", {})
        assert concurrency, "Workflow must have concurrency configuration"
        assert "group" in concurrency, "Concurrency must have group defined"
