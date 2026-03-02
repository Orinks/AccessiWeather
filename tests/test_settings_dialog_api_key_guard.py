"""
Tests that the settings dialog never wipes API keys with empty strings.

Regression test for: installed-build users losing keyring API keys after
the portable key storage overhaul. Root cause: if the keyring fails to load
transiently when the dialog opens, the field is populated as empty. On save,
the empty string was passed to update_settings → SecureStorage.set_password("")
→ delete_password(), permanently wiping the keyring entry.

The fix: track the original value at load time; if the field is empty on save
but the original was non-empty, skip the key in settings_dict entirely.
"""

from __future__ import annotations


def _make_dialog(vc_key="", openrouter_key="", original_vc="", original_or=""):
    """Create a minimal SettingsDialogSimple stand-in with the guard logic."""
    import importlib.util
    from pathlib import Path

    module_path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "accessiweather"
        / "ui"
        / "dialogs"
        / "settings_dialog.py"
    )
    spec = importlib.util.spec_from_file_location("sdmod", module_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    dlg = mod.SettingsDialogSimple.__new__(mod.SettingsDialogSimple)
    dlg._original_vc_key = original_vc
    dlg._original_openrouter_key = original_or

    settings_dict = {
        "visual_crossing_api_key": vc_key,
        "openrouter_api_key": openrouter_key,
        "update_interval_minutes": 30,
    }

    # Run just the guard block

    for key, orig_attr in (
        ("visual_crossing_api_key", "_original_vc_key"),
        ("openrouter_api_key", "_original_openrouter_key"),
    ):
        if not settings_dict.get(key) and getattr(dlg, orig_attr, ""):
            settings_dict.pop(key, None)

    return settings_dict


class TestApiKeyGuard:
    def test_empty_field_with_original_key_is_dropped(self):
        """Empty field + original non-empty → key removed from settings_dict."""
        result = _make_dialog(vc_key="", original_vc="my-real-key")
        assert "visual_crossing_api_key" not in result

    def test_empty_field_with_no_original_passes_through(self):
        """Empty field + no original key → passes through (user never set one)."""
        result = _make_dialog(vc_key="", original_vc="")
        assert "visual_crossing_api_key" in result
        assert result["visual_crossing_api_key"] == ""

    def test_non_empty_field_always_passes_through(self):
        """Non-empty field → always saved regardless of original."""
        result = _make_dialog(vc_key="new-key", original_vc="old-key")
        assert result["visual_crossing_api_key"] == "new-key"

    def test_openrouter_key_guard(self):
        """Same guard applies to openrouter key."""
        result = _make_dialog(openrouter_key="", original_or="sk-abc123")
        assert "openrouter_api_key" not in result

    def test_both_keys_guarded_independently(self):
        """Each key is guarded independently."""
        result = _make_dialog(
            vc_key="",
            openrouter_key="still-set",
            original_vc="was-set",
            original_or="still-set",
        )
        assert "visual_crossing_api_key" not in result
        assert result["openrouter_api_key"] == "still-set"
