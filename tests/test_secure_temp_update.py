"""Regression tests for secure temp directory usage in macOS update script."""

import tempfile
from pathlib import Path

from accessiweather.services.simple_update import plan_restart


class TestSecureTempUpdateScript:
    """Verify that macOS update script uses a unique temp directory, not a predictable path."""

    def test_should_use_mkdtemp_not_gettempdir(self):
        """Script path must be inside a unique mkdtemp directory, not directly in /tmp."""
        plan = plan_restart(
            update_path=Path("/tmp/fake_update.dmg"),
            portable=False,
            platform_system="darwin",
        )
        assert plan.script_path is not None
        # The parent should NOT be the system temp dir directly
        system_tmp = Path(tempfile.gettempdir())
        assert plan.script_path.parent != system_tmp, (
            f"Script path {plan.script_path} is directly in {system_tmp} — "
            "should be in a unique subdirectory"
        )
        # The parent should be a subdirectory of the system temp
        assert str(plan.script_path.parent).startswith(str(system_tmp))
        # The parent directory name should contain our prefix
        assert "accessiweather_update_" in plan.script_path.parent.name

    def test_should_create_unique_directories_per_call(self):
        """Each call should produce a different temp directory."""
        plan1 = plan_restart(
            update_path=Path("/tmp/fake1.dmg"), portable=False, platform_system="darwin"
        )
        plan2 = plan_restart(
            update_path=Path("/tmp/fake2.dmg"), portable=False, platform_system="darwin"
        )
        assert plan1.script_path is not None
        assert plan2.script_path is not None
        assert plan1.script_path.parent != plan2.script_path.parent

    def test_script_filename_is_preserved(self):
        """The script filename should still be accessiweather_update.sh."""
        plan = plan_restart(
            update_path=Path("/tmp/fake.dmg"), portable=False, platform_system="darwin"
        )
        assert plan.script_path is not None
        assert plan.script_path.name == "accessiweather_update.sh"
