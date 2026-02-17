"""wxPython UI components for AccessiWeather."""

import importlib as _importlib


def __getattr__(name):
    if name == "MainWindow":
        from .main_window import MainWindow

        return MainWindow
    # Allow submodule access (e.g. accessiweather.ui.dialogs)
    try:
        return _importlib.import_module(f".{name}", __name__)
    except ImportError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc


__all__ = ["MainWindow"]
