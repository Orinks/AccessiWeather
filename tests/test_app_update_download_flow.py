"""Coverage test for startup update download/apply flow."""

from __future__ import annotations

import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from accessiweather.app import AccessiWeatherApp


def test_download_and_apply_update_success_path(monkeypatch, tmp_path):
    import accessiweather.app as app_module
    import accessiweather.config_utils as config_utils
    import accessiweather.services.simple_update as simple_update

    progress_dialog = SimpleNamespace(
        Update=MagicMock(return_value=(True, False)), Destroy=MagicMock()
    )
    fake_wx = SimpleNamespace(
        PD_APP_MODAL=1,
        PD_AUTO_HIDE=2,
        PD_CAN_ABORT=4,
        YES_NO=8,
        ICON_QUESTION=16,
        YES=1,
        OK=32,
        ICON_ERROR=64,
        ProgressDialog=MagicMock(return_value=progress_dialog),
        MessageBox=MagicMock(return_value=1),
        CallAfter=lambda func, *args, **kwargs: func(*args, **kwargs),
        GetTopLevelWindows=MagicMock(return_value=[]),
        SafeYield=MagicMock(),
    )
    monkeypatch.setattr(app_module, "wx", fake_wx)

    class InlineThread:
        def __init__(self, target, daemon):
            self._target = target
            self.daemon = daemon

        def start(self):
            self._target()

    monkeypatch.setattr(threading, "Thread", InlineThread)

    class FakeUpdateService:
        def __init__(self, app_name):
            self.app_name = app_name

        async def download_update(self, update_info, dest_dir: Path, progress_callback):
            progress_callback(1024, 2048)
            return dest_dir / "accessiweather-update.zip"

        async def close(self):
            return None

    apply_update = MagicMock()
    monkeypatch.setattr(simple_update, "UpdateService", FakeUpdateService)
    monkeypatch.setattr(simple_update, "apply_update", apply_update)
    monkeypatch.setattr(config_utils, "is_portable_mode", MagicMock(return_value=False))

    app = AccessiWeatherApp.__new__(AccessiWeatherApp)
    app.main_window = None
    update_info = SimpleNamespace(artifact_name="accessiweather-update.zip")

    app._download_and_apply_update(update_info)

    fake_wx.ProgressDialog.assert_called_once()
    progress_dialog.Update.assert_called_once()
    assert "Downloading..." in progress_dialog.Update.call_args.args[1]
    apply_update.assert_called_once()
    assert apply_update.call_args.args[0].name == "accessiweather-update.zip"
    assert apply_update.call_args.kwargs == {"portable": False}
