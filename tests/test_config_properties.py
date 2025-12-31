"""Property-based tests for configuration serialization."""

from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis.strategies import (
    booleans,
    composite,
    dictionaries,
    floats,
    integers,
    lists,
    none,
    one_of,
    sampled_from,
    text,
)

from accessiweather.models.config import AppConfig, AppSettings
from accessiweather.models.weather import Location

# Strategies for generating valid values
temperature_units = sampled_from(["both", "fahrenheit", "celsius"])
data_sources = sampled_from(["auto", "nws", "open-meteo", "visual_crossing"])
update_channels = sampled_from(["stable", "beta", "dev"])
time_display_modes = sampled_from(["local", "utc"])


@composite
def valid_locations(draw) -> Location:
    """Generate valid Location objects."""
    name = draw(text(min_size=1, max_size=50).filter(lambda x: x.strip()))
    latitude = draw(floats(min_value=-90.0, max_value=90.0, allow_nan=False, allow_infinity=False))
    longitude = draw(
        floats(min_value=-180.0, max_value=180.0, allow_nan=False, allow_infinity=False)
    )
    country_code = draw(
        one_of(none(), text(min_size=2, max_size=2, alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ"))
    )
    return Location(name=name, latitude=latitude, longitude=longitude, country_code=country_code)


@composite
def valid_app_settings(draw) -> AppSettings:
    """Generate valid AppSettings objects."""
    return AppSettings(
        temperature_unit=draw(temperature_units),
        update_interval_minutes=draw(integers(min_value=1, max_value=1440)),
        show_detailed_forecast=draw(booleans()),
        enable_alerts=draw(booleans()),
        minimize_to_tray=draw(booleans()),
        startup_enabled=draw(booleans()),
        data_source=draw(data_sources),
        visual_crossing_api_key=draw(text(max_size=64)),
        auto_update_enabled=draw(booleans()),
        update_channel=draw(update_channels),
        update_check_interval_hours=draw(integers(min_value=1, max_value=168)),
        debug_mode=draw(booleans()),
        sound_enabled=draw(booleans()),
        sound_pack=draw(text(min_size=1, max_size=20).filter(lambda x: x.strip())),
        github_backend_url=draw(text(max_size=100)),
        github_app_id=draw(text(max_size=20)),
        github_app_private_key=draw(text(max_size=100)),
        github_app_installation_id=draw(text(max_size=20)),
        alert_notifications_enabled=draw(booleans()),
        alert_notify_extreme=draw(booleans()),
        alert_notify_severe=draw(booleans()),
        alert_notify_moderate=draw(booleans()),
        alert_notify_minor=draw(booleans()),
        alert_notify_unknown=draw(booleans()),
        alert_global_cooldown_minutes=draw(integers(min_value=0, max_value=60)),
        alert_per_alert_cooldown_minutes=draw(integers(min_value=0, max_value=1440)),
        alert_escalation_cooldown_minutes=draw(integers(min_value=0, max_value=60)),
        alert_freshness_window_minutes=draw(integers(min_value=1, max_value=60)),
        alert_max_notifications_per_hour=draw(integers(min_value=1, max_value=100)),
        alert_ignored_categories=draw(lists(text(min_size=1, max_size=20), max_size=5)),
        trend_insights_enabled=draw(booleans()),
        trend_hours=draw(integers(min_value=1, max_value=168)),
        show_dewpoint=draw(booleans()),
        show_pressure_trend=draw(booleans()),
        show_visibility=draw(booleans()),
        show_uv_index=draw(booleans()),
        air_quality_enabled=draw(booleans()),
        pollen_enabled=draw(booleans()),
        offline_cache_enabled=draw(booleans()),
        offline_cache_max_age_minutes=draw(integers(min_value=1, max_value=1440)),
        weather_history_enabled=draw(booleans()),
        time_display_mode=draw(time_display_modes),
        time_format_12hour=draw(booleans()),
        show_timezone_suffix=draw(booleans()),
        html_render_current_conditions=draw(booleans()),
        html_render_forecast=draw(booleans()),
        # AI Prompt Customization
        custom_system_prompt=draw(one_of(none(), text(max_size=500))),
        custom_instructions=draw(one_of(none(), text(max_size=200))),
    )


@composite
def valid_app_configs(draw) -> AppConfig:
    """Generate valid AppConfig objects."""
    settings = draw(valid_app_settings())
    locations = draw(lists(valid_locations(), max_size=5))
    current_location = draw(one_of(none(), valid_locations()))
    return AppConfig(settings=settings, locations=locations, current_location=current_location)


# Strategies for type coercion testing
bool_string_representations = sampled_from(
    ["true", "false", "True", "False", "TRUE", "FALSE", "1", "0", "yes", "no", "on", "off"]
)


@pytest.mark.unit
class TestAppSettingsRoundtrip:
    """Test AppSettings serialization roundtrip."""

    @given(valid_app_settings())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.differing_executors])
    def test_roundtrip_preserves_serializable_fields(self, settings_obj: AppSettings):
        """Roundtrip through to_dict/from_dict preserves serializable fields."""
        serialized = settings_obj.to_dict()
        restored = AppSettings.from_dict(serialized)

        # Check all fields that are in to_dict (excluding secrets stored in keyring)
        assert restored.temperature_unit == settings_obj.temperature_unit
        assert restored.update_interval_minutes == settings_obj.update_interval_minutes
        assert restored.show_detailed_forecast == settings_obj.show_detailed_forecast
        assert restored.enable_alerts == settings_obj.enable_alerts
        assert restored.minimize_to_tray == settings_obj.minimize_to_tray
        assert restored.startup_enabled == settings_obj.startup_enabled
        assert restored.data_source == settings_obj.data_source
        assert restored.auto_update_enabled == settings_obj.auto_update_enabled
        assert restored.update_channel == settings_obj.update_channel
        assert restored.update_check_interval_hours == settings_obj.update_check_interval_hours
        assert restored.debug_mode == settings_obj.debug_mode
        assert restored.sound_enabled == settings_obj.sound_enabled
        assert restored.sound_pack == settings_obj.sound_pack
        assert restored.github_backend_url == settings_obj.github_backend_url
        assert restored.alert_notifications_enabled == settings_obj.alert_notifications_enabled
        assert restored.alert_notify_extreme == settings_obj.alert_notify_extreme
        assert restored.alert_notify_severe == settings_obj.alert_notify_severe
        assert restored.alert_notify_moderate == settings_obj.alert_notify_moderate
        assert restored.alert_notify_minor == settings_obj.alert_notify_minor
        assert restored.alert_notify_unknown == settings_obj.alert_notify_unknown
        assert restored.alert_global_cooldown_minutes == settings_obj.alert_global_cooldown_minutes
        assert (
            restored.alert_per_alert_cooldown_minutes
            == settings_obj.alert_per_alert_cooldown_minutes
        )
        assert (
            restored.alert_escalation_cooldown_minutes
            == settings_obj.alert_escalation_cooldown_minutes
        )
        assert (
            restored.alert_freshness_window_minutes == settings_obj.alert_freshness_window_minutes
        )
        assert (
            restored.alert_max_notifications_per_hour
            == settings_obj.alert_max_notifications_per_hour
        )
        assert restored.alert_ignored_categories == settings_obj.alert_ignored_categories
        assert restored.trend_insights_enabled == settings_obj.trend_insights_enabled
        assert restored.trend_hours == settings_obj.trend_hours
        assert restored.show_dewpoint == settings_obj.show_dewpoint
        assert restored.show_pressure_trend == settings_obj.show_pressure_trend
        assert restored.show_visibility == settings_obj.show_visibility
        assert restored.show_uv_index == settings_obj.show_uv_index
        assert restored.air_quality_enabled == settings_obj.air_quality_enabled
        assert restored.pollen_enabled == settings_obj.pollen_enabled
        assert restored.offline_cache_enabled == settings_obj.offline_cache_enabled
        assert restored.offline_cache_max_age_minutes == settings_obj.offline_cache_max_age_minutes
        assert restored.weather_history_enabled == settings_obj.weather_history_enabled
        assert restored.time_display_mode == settings_obj.time_display_mode
        assert restored.time_format_12hour == settings_obj.time_format_12hour
        assert restored.show_timezone_suffix == settings_obj.show_timezone_suffix
        assert (
            restored.html_render_current_conditions == settings_obj.html_render_current_conditions
        )
        assert restored.html_render_forecast == settings_obj.html_render_forecast


@pytest.mark.unit
class TestAppSettingsUnknownKeys:
    """Test that unknown keys are ignored gracefully."""

    @given(dictionaries(text(min_size=1, max_size=20), text(max_size=50), max_size=10))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.differing_executors])
    def test_unknown_keys_ignored(self, extra_data: dict):
        """Unknown keys in input dict are ignored without exception."""
        # Add some unknown keys to a valid base dict
        base_data = {"temperature_unit": "celsius", "enable_alerts": True}
        data = {**base_data, **extra_data}

        # Should not raise
        settings_obj = AppSettings.from_dict(data)

        # Known fields should still work
        assert settings_obj.temperature_unit == "celsius"
        assert settings_obj.enable_alerts is True

    def test_completely_unknown_dict(self):
        """A dict with only unknown keys should return defaults."""
        data = {"unknown_key": "value", "another_unknown": 123, "nested": {"a": 1}}
        settings_obj = AppSettings.from_dict(data)

        # Should have default values
        assert settings_obj.temperature_unit == "both"
        assert settings_obj.update_interval_minutes == 10
        assert settings_obj.enable_alerts is True


@pytest.mark.unit
class TestAppSettingsDefaultValues:
    """Test that missing keys get default values."""

    def test_empty_dict_returns_defaults(self):
        """Empty dict should return all default values."""
        settings_obj = AppSettings.from_dict({})
        default = AppSettings()

        assert settings_obj.temperature_unit == default.temperature_unit
        assert settings_obj.update_interval_minutes == default.update_interval_minutes
        assert settings_obj.show_detailed_forecast == default.show_detailed_forecast
        assert settings_obj.enable_alerts == default.enable_alerts
        assert settings_obj.debug_mode == default.debug_mode

    @given(valid_app_settings())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.differing_executors])
    def test_partial_dict_fills_missing_with_defaults(self, settings_obj: AppSettings):
        """A partial dict should fill missing keys with defaults."""
        # Take only a subset of keys from a full settings object
        full_dict = settings_obj.to_dict()
        partial_dict = {"temperature_unit": full_dict["temperature_unit"]}

        restored = AppSettings.from_dict(partial_dict)
        default = AppSettings()

        # The provided key should match
        assert restored.temperature_unit == settings_obj.temperature_unit
        # Missing keys should be defaults
        assert restored.update_interval_minutes == default.update_interval_minutes
        assert restored.debug_mode == default.debug_mode


@pytest.mark.unit
class TestAppSettingsTypeCoercion:
    """Test type coercion for boolean fields."""

    @pytest.mark.parametrize(
        "string_val,expected",
        [
            ("true", True),
            ("True", True),
            ("TRUE", True),
            ("1", True),
            ("yes", True),
            ("on", True),
            ("false", False),
            ("False", False),
            ("FALSE", False),
            ("0", False),
            ("no", False),
            ("off", False),
        ],
    )
    def test_bool_string_coercion(self, string_val: str, expected: bool):
        """String representations of bools are properly converted."""
        data = {"enable_alerts": string_val, "debug_mode": string_val}
        settings_obj = AppSettings.from_dict(data)

        assert settings_obj.enable_alerts is expected
        assert settings_obj.debug_mode is expected

    @pytest.mark.parametrize(
        "int_val,expected",
        [
            (1, True),
            (0, False),
            (42, True),
            (-1, True),
        ],
    )
    def test_bool_int_coercion(self, int_val: int, expected: bool):
        """Integer representations are properly converted to bool."""
        data = {"enable_alerts": int_val}
        settings_obj = AppSettings.from_dict(data)

        assert settings_obj.enable_alerts is expected

    def test_none_uses_default(self):
        """None value should use the default."""
        data = {"enable_alerts": None, "debug_mode": None}
        settings_obj = AppSettings.from_dict(data)

        # enable_alerts defaults to True, debug_mode defaults to False
        assert settings_obj.enable_alerts is True
        assert settings_obj.debug_mode is False

    @given(
        text(min_size=1).filter(
            lambda x: x.lower() not in {"true", "false", "1", "0", "yes", "no", "on", "off"}
        )
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.differing_executors])
    def test_invalid_string_uses_default(self, invalid_str: str):
        """Invalid string values should use the default."""
        data = {"enable_alerts": invalid_str}
        settings_obj = AppSettings.from_dict(data)

        # enable_alerts defaults to True
        assert settings_obj.enable_alerts is True


@pytest.mark.unit
class TestLocationRoundtrip:
    """Test Location serialization through AppConfig."""

    @given(valid_locations())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.differing_executors])
    def test_location_roundtrip(self, location: Location):
        """Location data survives serialization roundtrip."""
        config = AppConfig(
            settings=AppSettings(),
            locations=[location],
            current_location=location,
        )

        serialized = config.to_dict()
        restored = AppConfig.from_dict(serialized)

        assert len(restored.locations) == 1
        restored_loc = restored.locations[0]

        assert restored_loc.name == location.name
        assert restored_loc.latitude == location.latitude
        assert restored_loc.longitude == location.longitude
        # country_code is uppercased in Location.__post_init__
        if location.country_code:
            assert restored_loc.country_code == location.country_code.upper()
        else:
            assert restored_loc.country_code is None

        # Check current_location
        assert restored.current_location is not None
        assert restored.current_location.name == location.name
        assert restored.current_location.latitude == location.latitude
        assert restored.current_location.longitude == location.longitude

    @given(lists(valid_locations(), min_size=0, max_size=10))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.differing_executors])
    def test_multiple_locations_roundtrip(self, locations: list[Location]):
        """Multiple locations survive serialization roundtrip."""
        config = AppConfig(
            settings=AppSettings(),
            locations=locations,
            current_location=None,
        )

        serialized = config.to_dict()
        restored = AppConfig.from_dict(serialized)

        assert len(restored.locations) == len(locations)
        for orig, rest in zip(locations, restored.locations, strict=False):
            assert rest.name == orig.name
            assert rest.latitude == orig.latitude
            assert rest.longitude == orig.longitude


@pytest.mark.unit
class TestAppConfigRoundtrip:
    """Test full AppConfig serialization roundtrip."""

    @given(valid_app_configs())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.differing_executors])
    def test_full_config_roundtrip(self, config: AppConfig):
        """Full AppConfig survives serialization roundtrip."""
        serialized = config.to_dict()
        restored = AppConfig.from_dict(serialized)

        # Check settings (subset of fields)
        assert restored.settings.temperature_unit == config.settings.temperature_unit
        assert restored.settings.enable_alerts == config.settings.enable_alerts
        assert restored.settings.debug_mode == config.settings.debug_mode

        # Check locations count
        assert len(restored.locations) == len(config.locations)

        # Check current_location
        if config.current_location is None:
            assert restored.current_location is None
        else:
            assert restored.current_location is not None
            assert restored.current_location.name == config.current_location.name

    def test_empty_config_roundtrip(self):
        """Empty config (default) survives roundtrip."""
        config = AppConfig.default()
        serialized = config.to_dict()
        restored = AppConfig.from_dict(serialized)

        assert len(restored.locations) == 0
        assert restored.current_location is None


@pytest.mark.unit
class TestEdgeCases:
    """Test edge cases in serialization."""

    def test_from_dict_with_empty_dict(self):
        """from_dict handles empty dict."""
        config = AppConfig.from_dict({})

        assert config.settings is not None
        assert config.locations == []
        assert config.current_location is None

    def test_from_dict_with_empty_locations_list(self):
        """from_dict handles empty locations list."""
        data = {"settings": {}, "locations": [], "current_location": None}
        config = AppConfig.from_dict(data)

        assert config.locations == []

    def test_from_dict_with_null_current_location(self):
        """from_dict handles null current_location."""
        data = {"settings": {}, "locations": [], "current_location": None}
        config = AppConfig.from_dict(data)

        assert config.current_location is None

    @given(lists(text(min_size=1, max_size=30), max_size=20))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.differing_executors])
    def test_alert_ignored_categories_roundtrip(self, categories: list[str]):
        """alert_ignored_categories list survives roundtrip."""
        settings_obj = AppSettings(alert_ignored_categories=categories)
        serialized = settings_obj.to_dict()
        restored = AppSettings.from_dict(serialized)

        assert restored.alert_ignored_categories == categories


@pytest.mark.unit
class TestPromptCustomizationRoundtrip:
    """
    Property tests for AI prompt customization configuration.

    **Feature: ai-prompt-customization, Property 3: Configuration persistence round-trip**
    **Validates: Requirements 1.4, 2.4**
    """

    @given(
        custom_system_prompt=one_of(none(), text(max_size=500)),
        custom_instructions=one_of(none(), text(max_size=200)),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.differing_executors])
    def test_prompt_settings_roundtrip(
        self, custom_system_prompt: str | None, custom_instructions: str | None
    ):
        """
        Test prompt settings survive serialization round-trip.

        *For any* valid prompt configuration (custom system prompt and custom instructions),
        saving to configuration and then loading should produce equivalent values.
        """
        settings_obj = AppSettings(
            custom_system_prompt=custom_system_prompt,
            custom_instructions=custom_instructions,
        )

        serialized = settings_obj.to_dict()
        restored = AppSettings.from_dict(serialized)

        assert restored.custom_system_prompt == custom_system_prompt
        assert restored.custom_instructions == custom_instructions

    def test_none_values_preserved(self):
        """None values for prompt settings are preserved through round-trip."""
        settings_obj = AppSettings(
            custom_system_prompt=None,
            custom_instructions=None,
        )

        serialized = settings_obj.to_dict()
        restored = AppSettings.from_dict(serialized)

        assert restored.custom_system_prompt is None
        assert restored.custom_instructions is None

    def test_empty_string_preserved(self):
        """Empty strings for prompt settings are preserved through round-trip."""
        settings_obj = AppSettings(
            custom_system_prompt="",
            custom_instructions="",
        )

        serialized = settings_obj.to_dict()
        restored = AppSettings.from_dict(serialized)

        assert restored.custom_system_prompt == ""
        assert restored.custom_instructions == ""

    def test_default_values(self):
        """Default values for prompt settings are None."""
        settings_obj = AppSettings()

        assert settings_obj.custom_system_prompt is None
        assert settings_obj.custom_instructions is None

    def test_missing_keys_use_defaults(self):
        """Missing prompt keys in dict use None defaults."""
        data = {"temperature_unit": "celsius"}
        settings_obj = AppSettings.from_dict(data)

        assert settings_obj.custom_system_prompt is None
        assert settings_obj.custom_instructions is None
