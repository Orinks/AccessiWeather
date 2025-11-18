"""Additional tests for AccessiWeatherApp main application."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from accessiweather.app import AccessiWeatherApp, main


class TestAccessiWeatherAppStartup:
    """Test AccessiWeatherApp startup and initialization."""

    @pytest.mark.asyncio
    async def test_handle_already_running_success(self):
        """Test handling when another instance is running."""
        app = Mock(spec=AccessiWeatherApp)
        app.single_instance_manager = Mock()
        app.single_instance_manager.show_already_running_dialog = AsyncMock()
        app.request_exit = Mock()

        # Call the method
        await AccessiWeatherApp._handle_already_running(app)

        app.single_instance_manager.show_already_running_dialog.assert_called_once()
        app.request_exit.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_already_running_exception(self):
        """Test handling exception in already running dialog."""
        app = Mock(spec=AccessiWeatherApp)
        app.single_instance_manager = Mock()
        app.single_instance_manager.show_already_running_dialog = AsyncMock(
            side_effect=Exception("Dialog error")
        )
        app.request_exit = Mock()

        # Should not raise exception, should still call request_exit
        await AccessiWeatherApp._handle_already_running(app)

        app.request_exit.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_running_success(self):
        """Test on_running method success path."""
        app = Mock(spec=AccessiWeatherApp)
        app.location_selection = Mock()
        app.location_selection.focus = Mock()
        app.refresh_button = Mock()
        app.update_task = None

        with (
            patch("accessiweather.app.app_helpers") as mock_helpers,
            patch("accessiweather.app.background_tasks") as mock_bg_tasks,
            patch("asyncio.create_task") as mock_create_task,
        ):
            mock_helpers.play_startup_sound = AsyncMock()
            mock_bg_tasks.start_background_updates = AsyncMock()
            mock_task = Mock()
            mock_task.add_done_callback = Mock()
            mock_create_task.return_value = mock_task

            await AccessiWeatherApp.on_running(app)

            mock_helpers.play_startup_sound.assert_called_once_with(app)
            mock_create_task.assert_called_once()
            mock_task.add_done_callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_running_focus_exception(self):
        """Test on_running when setting focus fails."""
        app = Mock(spec=AccessiWeatherApp)
        app.location_selection = Mock()
        app.location_selection.focus = Mock(side_effect=Exception("Focus error"))
        app.refresh_button = Mock()
        app.refresh_button.focus = Mock()
        app.update_task = None

        with (
            patch("accessiweather.app.app_helpers") as mock_helpers,
            patch("accessiweather.app.background_tasks") as mock_bg_tasks,
            patch("asyncio.create_task") as mock_create_task,
        ):
            mock_helpers.play_startup_sound = AsyncMock()
            mock_bg_tasks.start_background_updates = AsyncMock()
            mock_task = Mock()
            mock_task.add_done_callback = Mock()
            mock_create_task.return_value = mock_task

            # Should not raise exception
            await AccessiWeatherApp.on_running(app)

            # Should try fallback to refresh button
            app.refresh_button.focus.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_running_all_focus_fails(self):
        """Test on_running when all focus attempts fail."""
        app = Mock(spec=AccessiWeatherApp)
        app.location_selection = Mock()
        app.location_selection.focus = Mock(side_effect=Exception("Focus error 1"))
        app.refresh_button = Mock()
        app.refresh_button.focus = Mock(side_effect=Exception("Focus error 2"))
        app.update_task = None

        with (
            patch("accessiweather.app.app_helpers") as mock_helpers,
            patch("accessiweather.app.background_tasks") as mock_bg_tasks,
            patch("asyncio.create_task") as mock_create_task,
        ):
            mock_helpers.play_startup_sound = AsyncMock()
            mock_bg_tasks.start_background_updates = AsyncMock()
            mock_task = Mock()
            mock_task.add_done_callback = Mock()
            mock_create_task.return_value = mock_task

            # Should not raise exception
            await AccessiWeatherApp.on_running(app)

    @pytest.mark.asyncio
    async def test_on_running_background_task_exception(self):
        """Test on_running when background tasks fail."""
        app = Mock(spec=AccessiWeatherApp)
        app.location_selection = None
        app.refresh_button = None
        app.update_task = None

        with patch("accessiweather.app.app_helpers") as mock_helpers:
            mock_helpers.play_startup_sound = AsyncMock(side_effect=Exception("Sound error"))

            # Should not raise exception
            await AccessiWeatherApp.on_running(app)

    def test_initialize_components(self):
        """Test _initialize_components delegates to app_initialization."""
        app = Mock(spec=AccessiWeatherApp)

        with patch("accessiweather.app.app_initialization") as mock_init:
            AccessiWeatherApp._initialize_components(app)
            mock_init.initialize_components.assert_called_once_with(app)

    def test_load_initial_data(self):
        """Test _load_initial_data delegates to app_initialization."""
        app = Mock(spec=AccessiWeatherApp)

        with patch("accessiweather.app.app_initialization") as mock_init:
            AccessiWeatherApp._load_initial_data(app)
            mock_init.load_initial_data.assert_called_once_with(app)

    def test_on_window_close(self):
        """Test _on_window_close delegates to app_helpers."""
        app = Mock(spec=AccessiWeatherApp)
        widget = Mock()

        with patch("accessiweather.app.app_helpers") as mock_helpers:
            mock_helpers.handle_window_close.return_value = True
            result = AccessiWeatherApp._on_window_close(app, widget)
            mock_helpers.handle_window_close.assert_called_once_with(app, widget)
            assert result is True

    def test_on_exit(self):
        """Test on_exit delegates to app_helpers."""
        app = Mock(spec=AccessiWeatherApp)

        with patch("accessiweather.app.app_helpers") as mock_helpers:
            mock_helpers.handle_exit.return_value = None
            AccessiWeatherApp.on_exit(app)
            mock_helpers.handle_exit.assert_called_once_with(app)


class TestMainFunction:
    """Test main entry point."""

    def test_main_returns_app_instance(self):
        """Test that main() returns an AccessiWeatherApp instance."""
        with patch("accessiweather.app.AccessiWeatherApp.__init__", return_value=None):
            result = main()
            assert isinstance(result, AccessiWeatherApp)

    def test_main_app_configuration(self):
        """Test that main() configures the app correctly."""
        with patch("accessiweather.app.AccessiWeatherApp") as MockApp:
            main()
            MockApp.assert_called_once_with(
                "AccessiWeather",
                "net.orinks.accessiweather.simple",
                description="Simple, accessible weather application",
                home_page="https://github.com/Orinks/AccessiWeather",
                author="Orinks",
                config_dir=None,
                portable_mode=False,
            )
