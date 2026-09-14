"""Provider routing and secret persistence contracts."""

from unittest.mock import MagicMock, patch

import pytest

from accessiweather.ai_explainer_models import AIExplainerError
from accessiweather.ai_settings import explainer_options
from accessiweather.config.settings import SettingsOperations
from accessiweather.models import AppConfig, AppSettings


def test_existing_settings_keep_openrouter_defaults():
    settings = AppSettings.from_dict({})
    assert settings.ai_provider == "openrouter"
    assert settings.ai_model_preference == "openrouter/free"
    assert settings.venice_model == "venice-uncensored-1-2"


def test_round_trip_preserves_models_but_exports_neither_key():
    settings = AppSettings(
        ai_provider="venice",
        venice_model="custom-venice-model",
        ai_model_preference="custom-openrouter-model",
        venice_api_key="test-venice-secret",
        openrouter_api_key="test-openrouter-secret",
    )
    exported = settings.to_dict()
    assert "venice_api_key" not in exported
    assert "openrouter_api_key" not in exported
    restored = AppSettings.from_dict(exported)
    assert restored.ai_provider == "venice"
    assert restored.venice_model == "custom-venice-model"
    assert restored.ai_model_preference == "custom-openrouter-model"


def test_routing_never_borrows_other_providers_key_or_model():
    settings = AppSettings(ai_provider="venice", openrouter_api_key="test-openrouter-secret")
    options = explainer_options(settings)
    assert options["api_key"] is None
    assert options["provider"] == "venice"
    assert options["model"] == "venice-uncensored-1-2"
    settings.venice_api_key = "test-venice-secret"
    settings.custom_system_prompt = "Use plain language"
    settings.custom_instructions = "Focus on wind"
    assert explainer_options(settings)["api_key"] == "test-venice-secret"
    assert explainer_options(settings)["custom_system_prompt"] == "Use plain language"
    settings.ai_provider = "openrouter"
    assert explainer_options(settings)["api_key"] == "test-openrouter-secret"
    assert explainer_options(settings)["model"] == "openrouter/free"


def test_unknown_provider_does_not_silently_switch():
    with pytest.raises(AIExplainerError, match="Unknown AI provider"):
        explainer_options(AppSettings(ai_provider="unknown"))


def test_forecast_product_uses_selected_provider_and_portable_key():
    from types import SimpleNamespace

    from accessiweather.ui.dialogs.forecast_product_ai import build_explainer, has_openrouter_key

    settings = AppSettings(
        ai_provider="venice",
        venice_api_key="test-portable-key",
        venice_model="selected-venice-model",
        openrouter_api_key="test-other-key",
        custom_system_prompt="Use plain language",
        custom_instructions="Focus on wind",
    )
    app = SimpleNamespace(config_manager=SimpleNamespace(get_settings=lambda: settings))
    explainer = build_explainer(None, app)
    assert explainer.provider == "venice"
    assert explainer.api_key == "test-portable-key"
    assert explainer.get_effective_model() == "selected-venice-model"
    assert explainer.custom_system_prompt == "Use plain language"
    assert has_openrouter_key(app)
    settings.venice_api_key = ""
    assert not has_openrouter_key(app)


def test_venice_key_uses_secure_storage_and_is_redacted_from_logs():
    manager = MagicMock()
    manager.app._portable_mode = False
    manager.get_config.return_value = AppConfig.default()
    manager.save_config.return_value = True
    with patch(
        "accessiweather.config.settings.SecureStorage.set_password", return_value=True
    ) as save:
        assert SettingsOperations(manager).update_settings(venice_api_key="test-venice-secret")
    save.assert_called_once_with("venice_api_key", "test-venice-secret")
    assert "test-venice-secret" not in str(manager._get_logger.return_value.mock_calls)
