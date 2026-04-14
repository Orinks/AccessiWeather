from __future__ import annotations

import pathlib
from unittest.mock import MagicMock, patch

import pytest


class TestUserManualSource:
    @pytest.fixture
    def source(self):
        return pathlib.Path("src/accessiweather/ui/main_window.py").read_text()

    def test_help_menu_item_exists(self, source):
        assert "User &Manual" in source

    def test_help_menu_item_binds_handler(self, source):
        assert "_on_open_user_manual" in source

    def test_help_menu_item_uses_expected_label(self, source):
        assert '"User &Manual"' in source


def test_on_open_user_manual_calls_helper_without_error_dialog():
    from accessiweather.ui.main_window import MainWindow

    with patch.object(MainWindow, "__init__", lambda self, *a, **kw: None):
        win = MainWindow.__new__(MainWindow)

    with (
        patch("accessiweather.ui.main_window.open_user_manual", return_value=True) as open_mock,
        patch("accessiweather.ui.main_window.wx.MessageBox", create=True) as message_box,
    ):
        MainWindow._on_open_user_manual(win)

    open_mock.assert_called_once_with()
    message_box.assert_not_called()


def test_on_open_user_manual_shows_error_dialog_when_helper_fails():
    from accessiweather.ui.main_window import MainWindow

    with patch.object(MainWindow, "__init__", lambda self, *a, **kw: None):
        win = MainWindow.__new__(MainWindow)

    with (
        patch("accessiweather.ui.main_window.open_user_manual", return_value=False) as open_mock,
        patch("accessiweather.ui.main_window.wx.MessageBox", create=True) as message_box,
    ):
        MainWindow._on_open_user_manual(win)

    open_mock.assert_called_once_with()
    message_box.assert_called_once()


def test_get_bundled_user_manual_path_prefers_dev_docs(monkeypatch, tmp_path):
    project_root = tmp_path / "project"
    docs_dir = project_root / "docs"
    docs_dir.mkdir(parents=True)
    manual_path = docs_dir / "user_manual.md"
    manual_path.write_text("manual", encoding="utf-8")

    module_file = project_root / "src" / "accessiweather" / "user_manual.py"
    module_file.parent.mkdir(parents=True)
    module_file.write_text("# stub", encoding="utf-8")

    from accessiweather import user_manual

    monkeypatch.setattr(user_manual, "__file__", str(module_file))
    monkeypatch.delattr(user_manual.sys, "frozen", raising=False)
    monkeypatch.delattr(user_manual.sys, "_MEIPASS", raising=False)

    assert user_manual.get_bundled_user_manual_path() == manual_path


def test_get_bundled_user_manual_path_uses_meipass_when_frozen(monkeypatch, tmp_path):
    bundled_manual = tmp_path / "accessiweather" / "docs" / "user_manual.md"
    bundled_manual.parent.mkdir(parents=True)
    bundled_manual.write_text("manual", encoding="utf-8")

    from accessiweather import user_manual

    monkeypatch.setattr(user_manual.sys, "frozen", True, raising=False)
    monkeypatch.setattr(user_manual.sys, "_MEIPASS", str(tmp_path), raising=False)
    monkeypatch.setattr(user_manual.sys, "executable", str(tmp_path / "AccessiWeather.exe"), raising=False)

    assert user_manual.get_bundled_user_manual_path() == bundled_manual


def test_open_user_manual_opens_local_file_before_web_fallback(monkeypatch, tmp_path):
    manual_path = tmp_path / "user_manual.md"
    manual_path.write_text("manual", encoding="utf-8")

    from accessiweather import user_manual

    opened_urls: list[str] = []
    monkeypatch.setattr(user_manual, "get_bundled_user_manual_path", lambda: manual_path)
    monkeypatch.setattr(user_manual.webbrowser, "open", lambda url: opened_urls.append(url) or True)

    assert user_manual.open_user_manual() is True
    assert opened_urls == [manual_path.resolve().as_uri()]


def test_open_user_manual_falls_back_to_online_manual(monkeypatch):
    from accessiweather import user_manual

    opened_urls: list[str] = []
    monkeypatch.setattr(user_manual, "get_bundled_user_manual_path", lambda: None)
    monkeypatch.setattr(user_manual.webbrowser, "open", lambda url: opened_urls.append(url) or True)

    assert user_manual.open_user_manual() is True
    assert opened_urls == [user_manual.ONLINE_USER_MANUAL_URL]


def test_open_user_manual_returns_false_when_both_local_and_fallback_fail(monkeypatch, tmp_path):
    manual_path = tmp_path / "user_manual.md"
    manual_path.write_text("manual", encoding="utf-8")

    from accessiweather import user_manual

    open_mock = MagicMock(side_effect=[RuntimeError("local failed"), RuntimeError("web failed")])
    monkeypatch.setattr(user_manual, "get_bundled_user_manual_path", lambda: manual_path)
    monkeypatch.setattr(user_manual.webbrowser, "open", open_mock)

    assert user_manual.open_user_manual() is False
    assert open_mock.call_count == 2
