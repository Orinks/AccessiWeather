"""Tests for keyring availability warnings and portable re-prompt fix."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import wx

from accessiweather.app import AccessiWeatherApp


def _ensure_wx_constants():
    for name, value in {
        "OK": 0, "YES_NO": 0, "CANCEL": 0, "TE_PASSWORD": 0,
        "ICON_INFORMATION": 0, "ICON_WARNING": 0, "ICON_ERROR": 0,
        "ID_OK": 1, "ID_YES": 1, "ID_NO": 0, "ID_CANCEL": 2,
    }.items():
        if not hasattr(wx, name):
            setattr(wx, name, value)

_ensure_wx_constants()


def _make_wx_dialog(modal_result=None):
    dlg = MagicMock()
    dlg.ShowModal.return_value = modal_result if modal_result is not None else wx.ID_OK
    dlg.__enter__ = MagicMock(return_value=dlg)
    dlg.__exit__ = MagicMock(return_value=False)
    return dlg


def _make_app_stub(*, portable=False):
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)
    app._force_wizard = False
    app._portable_mode = portable
    app._portable_keys_imported_this_session = False
    app.debug_mode = False
    app.main_window = MagicMock()
    app.config_manager = MagicMock()
    settings = SimpleNamespace(
        onboarding_wizard_shown=False,
        portable_auto_bundle_enabled=False,
    )
    config = SimpleNamespace(settings=settings, locations={})
    app.config_manager.get_config.return_value = config
    app.config_manager.config_dir = MagicMock()
    return app


# ---------------------------------------------------------------------------
# is_keyring_available() unit tests
# ---------------------------------------------------------------------------

class TestIsKeyringAvailable:
    def setup_method(self):
        import accessiweather.config.secure_storage as ss
        ss._keyring_available = None
        ss._keyring_checked = False
        ss._keyring_module = None

    def teardown_method(self):
        import accessiweather.config.secure_storage as ss
        ss._keyring_available = None

    def test_returns_true_when_keyring_works(self):
        import accessiweather.config.secure_storage as ss
        mock_kr = MagicMock()
        mock_kr.get_password.return_value = "probe"
        with patch.object(ss, "_get_keyring", return_value=mock_kr):
            result = ss.is_keyring_available()
        assert result is True

    def test_returns_false_when_keyring_import_fails(self):
        import accessiweather.config.secure_storage as ss
        with patch.object(ss, "_get_keyring", return_value=None):
            result = ss.is_keyring_available()
        assert result is False

    def test_returns_false_when_roundtrip_raises(self):
        import accessiweather.config.secure_storage as ss
        mock_kr = MagicMock()
        mock_kr.set_password.side_effect = Exception("no backend")
        with patch.object(ss, "_get_keyring", return_value=mock_kr):
            result = ss.is_keyring_available()
        assert result is False

    def test_caches_result(self):
        import accessiweather.config.secure_storage as ss
        mock_kr = MagicMock()
        mock_kr.get_password.return_value = "probe"
        with patch.object(ss, "_get_keyring", return_value=mock_kr) as mock_get:
            ss.is_keyring_available()
            ss.is_keyring_available()
            assert mock_get.call_count == 1

    def test_returns_false_when_roundtrip_value_wrong(self):
        import accessiweather.config.secure_storage as ss
        mock_kr = MagicMock()
        mock_kr.get_password.return_value = "wrong"
        with patch.object(ss, "_get_keyring", return_value=mock_kr):
            result = ss.is_keyring_available()
        assert result is False


# ---------------------------------------------------------------------------
# Wizard warning tests
# ---------------------------------------------------------------------------

class TestWizardKeyringWarning:
    def setup_method(self):
        import accessiweather.config.secure_storage as ss
        ss._keyring_available = None

    def teardown_method(self):
        import accessiweather.config.secure_storage as ss
        ss._keyring_available = None

    def test_warning_shown_when_keyring_unavailable(self):
        import accessiweather.config.secure_storage as ss
        ss._keyring_available = False

        app = _make_app_stub()
        shown_titles = []

        if not hasattr(wx, "MessageDialog"):
            wx.MessageDialog = MagicMock

        def fake_msg_dialog(parent, msg, title, style=0):
            shown_titles.append(title)
            return _make_wx_dialog()

        with (
            patch("accessiweather.app.wx.MessageDialog", side_effect=fake_msg_dialog),
            patch.object(app, "_prompt_optional_secret_with_link", return_value=""),
            patch.object(app, "_should_show_first_start_onboarding", return_value=True),
            patch.object(app, "_run_deferred_startup_update_check"),
            patch.object(app, "_show_onboarding_readiness_summary"),
            patch.object(app, "_has_saved_api_key", return_value=False),
            patch.object(app, "_maybe_offer_portable_key_export"),
        ):
            app._maybe_show_first_start_onboarding()

        assert any("Secure storage unavailable" in t for t in shown_titles), \
            f"Expected warning dialog, got titles: {shown_titles}"

    def test_no_warning_when_keyring_available(self):
        import accessiweather.config.secure_storage as ss
        ss._keyring_available = True

        app = _make_app_stub()
        shown_titles = []

        def fake_msg_dialog(parent, msg, title, style=0):
            shown_titles.append(title)
            return _make_wx_dialog()

        with (
            patch("accessiweather.app.wx.MessageDialog", side_effect=fake_msg_dialog),
            patch.object(app, "_prompt_optional_secret_with_link", return_value=""),
            patch.object(app, "_should_show_first_start_onboarding", return_value=True),
            patch.object(app, "_run_deferred_startup_update_check"),
            patch.object(app, "_show_onboarding_readiness_summary"),
            patch.object(app, "_has_saved_api_key", return_value=False),
            patch.object(app, "_maybe_offer_portable_key_export"),
        ):
            app._maybe_show_first_start_onboarding()

        assert not any("Secure storage unavailable" in t for t in shown_titles)

    def test_wizard_continues_after_warning(self):
        import accessiweather.config.secure_storage as ss
        ss._keyring_available = False

        app = _make_app_stub()
        prompt_calls = []

        def fake_prompt(*args, **kwargs):
            prompt_calls.append(args)
            return ""

        with (
            patch("accessiweather.app.wx.MessageDialog", side_effect=lambda *a, **k: _make_wx_dialog()),
            patch.object(app, "_prompt_optional_secret_with_link", side_effect=fake_prompt),
            patch.object(app, "_should_show_first_start_onboarding", return_value=True),
            patch.object(app, "_run_deferred_startup_update_check"),
            patch.object(app, "_show_onboarding_readiness_summary"),
            patch.object(app, "_has_saved_api_key", return_value=False),
            patch.object(app, "_maybe_offer_portable_key_export"),
        ):
            app._maybe_show_first_start_onboarding()

        assert len(prompt_calls) == 2


# ---------------------------------------------------------------------------
# Portable session flag tests
# ---------------------------------------------------------------------------

class TestPortableSessionFlag:
    def test_session_flag_prevents_re_prompt(self):
        app = _make_app_stub(portable=True)
        app._portable_keys_imported_this_session = True

        with patch.object(app, "_has_any_saved_api_keys") as mock_check:
            app._maybe_auto_import_keys_file()
            mock_check.assert_not_called()

    def test_session_flag_false_by_default(self):
        app = _make_app_stub(portable=True)
        assert app._portable_keys_imported_this_session is False

    def test_auto_import_runs_when_flag_not_set(self):
        """Without session flag, _has_any_saved_api_keys should be consulted."""
        app = _make_app_stub(portable=True)
        app._portable_keys_imported_this_session = False

        if not hasattr(wx, "TextEntryDialog"):
            wx.TextEntryDialog = MagicMock

        with (
            patch.object(app, "_has_any_saved_api_keys", return_value=True) as mock_check,
            patch("accessiweather.app.wx.TextEntryDialog", return_value=_make_wx_dialog(), create=True),
            patch("accessiweather.app.wx.MessageBox", create=True),
        ):
            app._maybe_auto_import_keys_file()
            mock_check.assert_called_once()
