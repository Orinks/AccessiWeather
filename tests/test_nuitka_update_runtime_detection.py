from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock


class _ThreadStub:
    created = False

    def __init__(self, target, daemon=False):
        self.target = target
        self.daemon = daemon
        type(self).created = True

    def start(self):
        pass


def test_main_window_update_check_allows_nuitka_runtime(monkeypatch):
    from accessiweather.ui import main_window

    win = main_window.MainWindow.__new__(main_window.MainWindow)
    win.app = SimpleNamespace(version="0.6.1.dev0", build_tag="nightly-20260428")
    win._get_update_channel = lambda: "nightly"

    _ThreadStub.created = False
    message_box = MagicMock()
    monkeypatch.setattr(main_window, "is_compiled_runtime", lambda: True)
    monkeypatch.setattr(main_window.wx, "MessageBox", message_box)
    monkeypatch.setattr(main_window.wx, "BeginBusyCursor", MagicMock())
    monkeypatch.setattr("threading.Thread", _ThreadStub)

    main_window.MainWindow._on_check_updates(win)

    message_box.assert_not_called()
    assert _ThreadStub.created is True


def test_settings_dialog_update_check_allows_nuitka_runtime(monkeypatch):
    from accessiweather.ui.dialogs import settings_dialog

    dialog = settings_dialog.SettingsDialogSimple.__new__(settings_dialog.SettingsDialogSimple)
    dialog.app = SimpleNamespace(version="0.6.1.dev0", build_tag="nightly-20260428")
    status = MagicMock()
    channel = MagicMock()
    channel.GetSelection.return_value = 1
    dialog._controls = {"update_status": status, "update_channel": channel}

    _ThreadStub.created = False
    message_box = MagicMock()
    monkeypatch.setattr(settings_dialog, "is_compiled_runtime", lambda: True)
    monkeypatch.setattr(settings_dialog.wx, "MessageBox", message_box)
    monkeypatch.setattr("threading.Thread", _ThreadStub)

    settings_dialog.SettingsDialogSimple._on_check_updates(dialog, None)

    message_box.assert_not_called()
    status.SetLabel.assert_called_once_with("Checking for updates...")
    assert _ThreadStub.created is True
