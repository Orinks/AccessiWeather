from __future__ import annotations

from unittest.mock import MagicMock, patch


def _make_app():
    from accessiweather.app import AccessiWeatherApp

    with patch.object(AccessiWeatherApp, "__init__", lambda self, *a, **kw: None):
        app = AccessiWeatherApp.__new__(AccessiWeatherApp)

    app.main_window = MagicMock()
    return app


def test_ctrl_1_shortcut_focuses_current_conditions_section():
    app = _make_app()

    app._on_focus_current_conditions_shortcut(None)

    app.main_window.focus_section_by_number.assert_called_once_with(1)


def test_ctrl_5_shortcut_focuses_event_center_section():
    app = _make_app()

    app._on_focus_event_center_shortcut(None)

    app.main_window.focus_section_by_number.assert_called_once_with(5)
