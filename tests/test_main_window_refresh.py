from unittest.mock import MagicMock, patch


def test_on_refresh_forces_refresh():
    from accessiweather.ui.main_window import MainWindow

    with patch.object(MainWindow, "__init__", lambda self, *a, **kw: None):
        win = MainWindow.__new__(MainWindow)

    win.refresh_weather_async = MagicMock()

    win.on_refresh()

    win.refresh_weather_async.assert_called_once_with(force_refresh=True)
