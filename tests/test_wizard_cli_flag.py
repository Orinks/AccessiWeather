"""Tests for the --wizard CLI flag that forces the onboarding wizard."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from accessiweather.app import AccessiWeatherApp


def _make_app(*, force_wizard: bool = False, debug: bool = False) -> AccessiWeatherApp:
    """Create a bare AccessiWeatherApp instance without calling __init__."""
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)
    app._force_wizard = force_wizard
    app.debug_mode = debug
    app.main_window = MagicMock()
    settings = SimpleNamespace(onboarding_wizard_shown=True)
    config = SimpleNamespace(settings=settings, locations={"Home": object()})
    app.config_manager = SimpleNamespace(get_config=lambda: config)
    return app


class TestShouldShowFirstStartOnboarding:
    def test_returns_false_normally_when_wizard_shown_and_has_locations(self):
        app = _make_app(force_wizard=False)
        assert app._should_show_first_start_onboarding() is False

    def test_force_wizard_overrides_shown_flag(self):
        """--wizard should return True even when onboarding_wizard_shown=True."""
        app = _make_app(force_wizard=True)
        assert app._should_show_first_start_onboarding() is True

    def test_force_wizard_overrides_existing_locations(self):
        """--wizard should return True even when locations exist."""
        app = _make_app(force_wizard=True)
        assert app._should_show_first_start_onboarding() is True

    def test_no_main_window_returns_false_even_with_force_wizard(self):
        app = _make_app(force_wizard=True)
        app.main_window = None
        assert app._should_show_first_start_onboarding() is False

    def test_no_config_manager_returns_false_even_with_force_wizard(self):
        app = _make_app(force_wizard=True)
        app.config_manager = None
        assert app._should_show_first_start_onboarding() is False

    def test_debug_mode_logs_when_wizard_forced(self, caplog):
        import logging

        app = _make_app(force_wizard=True, debug=True)
        with caplog.at_level(logging.DEBUG, logger="accessiweather.app"):
            app._should_show_first_start_onboarding()
        assert any("--wizard flag" in r.message for r in caplog.records)

    def test_no_debug_log_without_debug_mode(self, caplog):
        import logging

        app = _make_app(force_wizard=True, debug=False)
        with caplog.at_level(logging.DEBUG, logger="accessiweather.app"):
            app._should_show_first_start_onboarding()
        assert not any("--wizard flag" in r.message for r in caplog.records)


class TestMainFunctionForceWizard:
    def test_main_passes_force_wizard_to_app(self):
        """main() should pass force_wizard to AccessiWeatherApp."""
        with (
            patch("accessiweather.app.AccessiWeatherApp") as MockApp,
            patch(
                "accessiweather.app._explicit_portable_config_dir", return_value=None, create=True
            ),
        ):
            mock_instance = MagicMock()
            MockApp.return_value = mock_instance

            from accessiweather.app import main

            main(force_wizard=True)

            call_kwargs = MockApp.call_args[1] if MockApp.call_args[1] else {}
            # force_wizard should be passed as a kwarg
            assert call_kwargs.get("force_wizard") is True


class TestArgparse:
    def test_wizard_flag_parsed(self):
        """__main__.parse_args should recognise --wizard."""
        import sys

        from accessiweather.__main__ import parse_args

        old_argv = sys.argv
        try:
            sys.argv = ["accessiweather", "--wizard"]
            args = parse_args()
            assert args.wizard is True
        finally:
            sys.argv = old_argv

    def test_wizard_defaults_to_false(self):
        import sys

        from accessiweather.__main__ import parse_args

        old_argv = sys.argv
        try:
            sys.argv = ["accessiweather"]
            args = parse_args()
            assert args.wizard is False
        finally:
            sys.argv = old_argv
