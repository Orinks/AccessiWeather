"""AI settings preserve independent provider configuration and shared prompts."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from accessiweather.ui.dialogs.settings_tabs.ai import AITab


class Control:
    def __init__(self):
        """Start with an empty control value."""
        self.value = ""
        self.selection = 0
        self.name = ""

    def SetValue(self, value):
        self.value = value

    def GetValue(self):
        return self.value

    def SetSelection(self, value):
        self.selection = value

    def GetSelection(self):
        return self.selection

    def Bind(self, *args):
        pass

    def Append(self, value):
        pass

    def SetName(self, name):
        self.name = name


def make_tab():
    controls = {
        key: Control()
        for key in (
            "ai_provider",
            "venice_key",
            "venice_model",
            "validate_venice_key",
            "get_venice_key",
            "openrouter_key",
            "ai_model",
            "ai_style",
            "custom_prompt",
            "custom_instructions",
        )
    }
    dialog = SimpleNamespace(
        _controls=controls, _get_ai_model_preference=MagicMock(return_value="openrouter/free")
    )
    return AITab(dialog), controls


def test_switch_provider_preserves_both_credentials_models_and_prompts():
    tab, controls = make_tab()
    tab.load(
        SimpleNamespace(
            ai_provider="venice",
            venice_api_key="venice-test",
            venice_model="custom-venice-model",
            openrouter_api_key="openrouter-test",
            ai_model_preference="openrouter/free",
            custom_system_prompt="My system prompt",
            custom_instructions="My instructions",
        )
    )
    assert controls["ai_provider"].GetSelection() == 1
    for selection, provider in [(0, "openrouter"), (1, "venice")]:
        controls["ai_provider"].SetSelection(selection)
        saved = tab.save()
        assert saved["ai_provider"] == provider
        assert saved["venice_api_key"] == "venice-test"
        assert saved["venice_model"] == "custom-venice-model"
        assert saved["openrouter_api_key"] == "openrouter-test"
        assert saved["ai_model_preference"] == "openrouter/free"
        assert saved["custom_system_prompt"] == "My system prompt"
        assert saved["custom_instructions"] == "My instructions"


def test_legacy_settings_keep_openrouter_default_and_name_new_controls():
    tab, controls = make_tab()
    tab.load(SimpleNamespace())
    tab.setup_accessibility()
    assert tab.save()["ai_provider"] == "openrouter"
    assert tab.save()["venice_model"] == "venice-uncensored-1-2"
    assert controls["ai_provider"].name == "AI provider"
    assert controls["venice_key"].name == "Venice API key"
    assert controls["venice_model"].name == "Venice model ID"


def test_retired_llama_preference_loads_as_browsed_model_not_preset():
    tab, controls = make_tab()
    tab.load(SimpleNamespace(ai_model_preference="meta-llama/llama-3.3-70b-instruct:free"))
    assert controls["ai_model"].GetSelection() == 2
    assert tab.dialog._selected_specific_model == "meta-llama/llama-3.3-70b-instruct:free"


def test_paid_router_preference_maps_to_second_picker_entry():
    tab, controls = make_tab()
    tab.load(SimpleNamespace(ai_model_preference="auto"))
    assert controls["ai_model"].GetSelection() == 1


def test_missing_venice_key_focuses_credential_field(monkeypatch):
    from accessiweather.ui.dialogs import settings_dialog_handlers as handlers

    message = MagicMock()
    monkeypatch.setattr(handlers.wx, "MessageBox", message)
    key = MagicMock()
    key.GetValue.return_value = "  "
    dialog = SimpleNamespace(_controls={"venice_key": key})
    handlers.SettingsDialogHandlersMixin._on_validate_venice_key(dialog, None)
    key.SetFocus.assert_called_once()
    assert "enter your Venice API key" in message.call_args.args[0]


def test_validation_exception_does_not_expose_secret(monkeypatch):
    import threading

    from accessiweather import ai_provider
    from accessiweather.ui.dialogs import settings_dialog_handlers as handlers

    monkeypatch.setattr(
        ai_provider,
        "validate_venice_api_key",
        AsyncMock(side_effect=RuntimeError("secret-test-key")),
    )
    monkeypatch.setattr(threading, "Thread", lambda target, **kwargs: SimpleNamespace(start=target))
    monkeypatch.setattr(handlers.wx, "CallAfter", lambda fn, *args: fn(*args))
    message = MagicMock()
    monkeypatch.setattr(handlers.wx, "MessageBox", message)
    key = MagicMock()
    key.GetValue.return_value = "secret-test-key"
    button = MagicMock()
    dialog = SimpleNamespace(
        _controls={"venice_key": key, "validate_venice_key": button},
        IsBeingDeleted=lambda: False,
        _venice_validation_announcer=MagicMock(),
    )
    handlers.SettingsDialogHandlersMixin._on_validate_venice_key(dialog, None)
    assert "secret-test-key" not in message.call_args.args[0]
    assert "connection" in message.call_args.args[0]
    button.Disable.assert_called_once()
    button.Enable.assert_called_once()
    button.SetFocus.assert_called_once()


def test_validation_announces_progress_and_restores_focus_after_completion(monkeypatch):
    import threading

    from accessiweather import ai_provider
    from accessiweather.ui.dialogs import settings_dialog_handlers as handlers

    pending = []
    monkeypatch.setattr(
        threading,
        "Thread",
        lambda target, **kwargs: SimpleNamespace(start=lambda: pending.append(target)),
    )
    monkeypatch.setattr(
        ai_provider,
        "validate_venice_api_key",
        AsyncMock(return_value=(True, "Venice key is valid.")),
    )
    monkeypatch.setattr(handlers.wx, "CallAfter", lambda fn, *args: fn(*args))
    message = MagicMock()
    monkeypatch.setattr(handlers.wx, "MessageBox", message)
    key = MagicMock()
    key.GetValue.return_value = "test-key"
    button = MagicMock()
    announcer = MagicMock()
    dialog = SimpleNamespace(
        _controls={"venice_key": key, "validate_venice_key": button},
        IsBeingDeleted=lambda: False,
        _venice_validation_announcer=announcer,
    )
    handlers.SettingsDialogHandlersMixin._on_validate_venice_key(dialog, None)
    button.Disable.assert_called_once()
    key.SetFocus.assert_called_once()
    announcer.announce.assert_called_once_with("Validating Venice key…")
    button.Enable.assert_not_called()
    message.assert_not_called()
    pending[0]()
    button.Enable.assert_called_once()
    button.SetFocus.assert_called_once()
    assert message.call_args.args[0] == "Venice key is valid."


class Panel:
    def __init__(self):
        """Track visibility like a wx.Window."""
        self.shown = True

    def Show(self, show=True):
        self.shown = bool(show)

    def IsShown(self):
        return self.shown


def make_tab_with_panels():
    tab, controls = make_tab()
    tab._provider_panels = {"openrouter": Panel(), "venice": Panel()}
    tab._panel = MagicMock()
    return tab, controls


def test_only_selected_provider_section_is_shown():
    tab, controls = make_tab_with_panels()
    tab.load(SimpleNamespace(ai_provider="venice"))
    assert not tab._provider_panels["openrouter"].IsShown()
    assert tab._provider_panels["venice"].IsShown()

    controls["ai_provider"].SetSelection(0)
    tab._on_provider_changed(None)
    assert tab._provider_panels["openrouter"].IsShown()
    assert not tab._provider_panels["venice"].IsShown()


def test_load_without_built_panels_does_not_fail():
    tab, _controls = make_tab()
    tab.load(SimpleNamespace(ai_provider="venice"))
