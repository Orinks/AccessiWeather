"""
Tests for system tray functionality and window management.

These tests verify the correctness properties defined in the design document
for the forecast-navigation-improvements feature.

**Feature: forecast-navigation-improvements**
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import (
    HealthCheck,
    given,
    settings,
    strategies as st,
)

# Set TOGA_BACKEND before importing toga
os.environ.setdefault("TOGA_BACKEND", "toga_dummy")


from accessiweather import app_helpers  # noqa: E402

if TYPE_CHECKING:
    pass


# -----------------------------------------------------------------------------
# Mock App Factory
# -----------------------------------------------------------------------------


def create_mock_app(
    minimize_to_tray: bool = False,
    system_tray_available: bool = True,
    window_visible: bool = True,
    has_dialogs: bool = False,
) -> MagicMock:
    """Create a mock AccessiWeatherApp for testing."""
    app = MagicMock()

    # Config manager mock
    config = MagicMock()
    config.settings.minimize_to_tray = minimize_to_tray
    app.config_manager.get_config.return_value = config

    # System tray state
    app.system_tray_available = system_tray_available
    app.status_icon = MagicMock() if system_tray_available else None
    app.window_visible = window_visible

    # Main window mock
    app.main_window = MagicMock()
    app.main_window.visible = window_visible
    app.main_window.hide = MagicMock()
    app.main_window.show = MagicMock()

    # Show/hide command mock
    app.show_hide_command = MagicMock()
    app.show_hide_command.text = (
        "Show AccessiWeather" if not window_visible else "Hide AccessiWeather"
    )

    # Windows (dialogs) mock
    if has_dialogs:
        dialog = MagicMock()
        dialog.visible = True
        app.windows = [app.main_window, dialog]
    else:
        app.windows = [app.main_window]

    return app


# -----------------------------------------------------------------------------
# Hypothesis Strategies
# -----------------------------------------------------------------------------

app_state_strategy = st.fixed_dictionaries(
    {
        "minimize_to_tray": st.booleans(),
        "system_tray_available": st.booleans(),
        "window_visible": st.booleans(),
        "has_dialogs": st.booleans(),
    }
)


# -----------------------------------------------------------------------------
# Property Tests for System Tray
# -----------------------------------------------------------------------------


@pytest.mark.unit
class TestSystemTrayStateConsistencyProperty:
    """
    Property 4: System tray minimize behavior.

    *For any* application state where minimize-to-tray is enabled, when the user
    triggers minimize (via window close or Escape key), the main window should
    become hidden and the system tray icon should remain visible.

    **Validates: Requirements 2.1, 2.2, 4.1**
    """

    @given(state=app_state_strategy)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_minimize_behavior_consistency(self, state: dict) -> None:
        """
        **Feature: forecast-navigation-improvements, Property 4: System tray minimize behavior.**.

        For any application state, minimize behavior should be consistent:
        - If minimize_to_tray enabled AND tray available: window hides
        - If minimize_to_tray enabled but tray unavailable: window minimizes to taskbar
        - If minimize_to_tray disabled: window close exits app
        """
        app = create_mock_app(**state)

        # Simulate window close
        result = app_helpers.handle_window_close(app, None)

        if state["minimize_to_tray"]:
            # Should not exit (return False)
            assert result is False, "Should not exit when minimize_to_tray is enabled"

            if state["system_tray_available"]:
                # Window should be hidden
                app.main_window.hide.assert_called_once()
            # If tray unavailable, minimize to taskbar is attempted
        else:
            # Should exit (return True)
            assert result is True, "Should exit when minimize_to_tray is disabled"


# -----------------------------------------------------------------------------
# Property Tests for Escape Key
# -----------------------------------------------------------------------------


@pytest.mark.unit
class TestEscapeKeyContextAwarenessProperty:
    """
    Property 6: Escape key context awareness.

    *For any* application state with an open modal dialog, when the user presses
    Escape, the dialog should close without minimizing the main window.

    **Validates: Requirements 4.2**
    """

    @given(state=app_state_strategy)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_escape_key_with_dialog_does_not_minimize(self, state: dict) -> None:
        """
        **Feature: forecast-navigation-improvements, Property 6: Escape key context awareness.**.

        For any application state with a dialog open, Escape should not minimize.
        """
        # Force dialog to be open
        state_with_dialog = {**state, "has_dialogs": True}
        app = create_mock_app(**state_with_dialog)

        result = app_helpers.handle_escape_key(app)

        # Should return False (not handled) when dialog is open
        assert result is False, "Escape should not be handled when dialog is open"
        # Window should NOT be hidden
        app.main_window.hide.assert_not_called()

    @given(state=app_state_strategy)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_escape_key_without_dialog_always_minimizes(self, state: dict) -> None:
        """
        **Feature: forecast-navigation-improvements, Property 6: Escape key context awareness.**.

        For any application state without dialogs, Escape should always minimize
        (regardless of minimize_to_tray setting - that only affects window close behavior).
        """
        # Force no dialogs
        state_no_dialog = {**state, "has_dialogs": False}
        app = create_mock_app(**state_no_dialog)

        result = app_helpers.handle_escape_key(app)

        # Escape should always be handled (minimize) when no dialog is open
        assert result is True, "Escape should always minimize when no dialog is open"
        if state["system_tray_available"]:
            app.main_window.hide.assert_called_once()


@pytest.mark.unit
class TestFallbackMinimizeBehaviorProperty:
    """
    Property 8: Fallback minimize behavior.

    *For any* application state where system tray is unavailable or disabled,
    when the user presses Escape or closes the window, the window should minimize
    to the taskbar instead of hiding completely.

    **Validates: Requirements 4.4, 4.5**
    """

    @given(minimize_enabled=st.booleans())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_fallback_to_taskbar_when_tray_unavailable(self, minimize_enabled: bool) -> None:
        """
        **Feature: forecast-navigation-improvements, Property 8: Fallback minimize behavior.**.

        When system tray is unavailable, minimize should fall back to taskbar.
        """
        app = create_mock_app(
            minimize_to_tray=minimize_enabled,
            system_tray_available=False,
            window_visible=True,
            has_dialogs=False,
        )

        result = app_helpers.handle_window_close(app, None)

        if minimize_enabled:
            # Should not exit
            assert result is False
            # Window should NOT be hidden (no tray)
            app.main_window.hide.assert_not_called()
            # Should attempt to minimize to taskbar (state = "minimized")
        else:
            # Should exit
            assert result is True


# -----------------------------------------------------------------------------
# Unit Tests for System Tray Initialization
# -----------------------------------------------------------------------------


@pytest.mark.unit
class TestSystemTrayInitialization:
    """Unit tests for system tray initialization (Task 2.2)."""

    def test_successful_initialization(self) -> None:
        """Test system tray initializes successfully."""
        from accessiweather.ui_builder import initialize_system_tray

        app = MagicMock()
        app.status_icons = MagicMock()
        app.status_icons.commands = MagicMock()
        app.icon = MagicMock()
        app.icon.paths = ["/path/to/icon.png"]

        # Mock toga.MenuStatusIcon to avoid actual creation
        with patch("accessiweather.ui_builder.toga.MenuStatusIcon") as mock_status_icon:
            mock_status_icon.return_value = MagicMock()
            result = initialize_system_tray(app)

        assert result is True
        assert app.system_tray_available is True
        assert app.status_icon is not None
        app.status_icons.add.assert_called_once()

    def test_initialization_without_status_icons(self) -> None:
        """Test system tray handles missing status_icons attribute."""
        from accessiweather.ui_builder import initialize_system_tray

        app = MagicMock(spec=[])  # No attributes

        result = initialize_system_tray(app)

        assert result is False
        assert app.system_tray_available is False

    def test_initialization_failure_handling(self) -> None:
        """Test system tray handles initialization errors gracefully."""
        from accessiweather.ui_builder import initialize_system_tray

        app = MagicMock()
        app.status_icons = MagicMock()
        app.status_icons.add.side_effect = Exception("Test error")
        app.icon = MagicMock()

        result = initialize_system_tray(app)

        assert result is False
        assert app.system_tray_available is False


# -----------------------------------------------------------------------------
# Unit Tests for Window Management
# -----------------------------------------------------------------------------


@pytest.mark.unit
class TestWindowManagement:
    """Unit tests for window management (Task 3.3)."""

    def test_minimize_to_tray_when_enabled(self) -> None:
        """Test window hides to tray when minimize_to_tray is enabled."""
        app = create_mock_app(minimize_to_tray=True, system_tray_available=True)

        result = app_helpers.handle_window_close(app, None)

        assert result is False
        app.main_window.hide.assert_called_once()

    def test_minimize_to_taskbar_when_tray_disabled(self) -> None:
        """Test window minimizes to taskbar when tray is disabled."""
        app = create_mock_app(minimize_to_tray=True, system_tray_available=False)

        result = app_helpers.handle_window_close(app, None)

        assert result is False
        app.main_window.hide.assert_not_called()

    def test_exit_when_minimize_disabled(self) -> None:
        """Test app exits when minimize_to_tray is disabled."""
        app = create_mock_app(minimize_to_tray=False)

        result = app_helpers.handle_window_close(app, None)

        assert result is True

    def test_escape_key_with_open_dialog(self) -> None:
        """Test Escape key doesn't minimize when dialog is open."""
        app = create_mock_app(minimize_to_tray=True, has_dialogs=True)

        result = app_helpers.handle_escape_key(app)

        assert result is False
        app.main_window.hide.assert_not_called()

    def test_escape_key_without_dialog(self) -> None:
        """Test Escape key minimizes when no dialog is open."""
        app = create_mock_app(minimize_to_tray=True, system_tray_available=True, has_dialogs=False)

        result = app_helpers.handle_escape_key(app)

        assert result is True
        app.main_window.hide.assert_called_once()

    def test_is_escape_key_detection(self) -> None:
        """Test escape key detection function."""
        assert app_helpers.is_escape_key("escape") is True
        assert app_helpers.is_escape_key("Escape") is True
        assert app_helpers.is_escape_key("ESC") is True
        assert app_helpers.is_escape_key("esc") is True
        assert app_helpers.is_escape_key("<Key.ESCAPE>") is True
        assert app_helpers.is_escape_key("Key.escape") is True
        assert app_helpers.is_escape_key("enter") is False
        assert app_helpers.is_escape_key("a") is False
