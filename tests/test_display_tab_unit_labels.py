"""Tests for issue #558 — temperature unit preference labels are Auto/Imperial/Metric."""

from __future__ import annotations

import pytest

from accessiweather.ui.dialogs.settings_tabs.display import (
    _TEMP_MAP,
    _TEMP_VALUES,
)


class TestTempUnitChoiceLabels:
    """The UI choices must use the new Auto/Imperial/Metric naming convention."""

    def test_choices_list_length(self):
        # Four options: Auto, Imperial, Metric, Both
        # (verified via _TEMP_VALUES mapping)
        assert len(_TEMP_VALUES) == 4

    @pytest.mark.parametrize(
        "label",
        [
            "Fahrenheit only",
            "Celsius only",
            "Both (Fahrenheit and Celsius)",
        ],
    )
    def test_old_labels_not_present_in_module(self, label):
        """Old Fahrenheit/Celsius/Both labels must not appear in display module source."""
        import inspect

        import accessiweather.ui.dialogs.settings_tabs.display as display_module

        source = inspect.getsource(display_module)
        assert label not in source, f"Old label '{label}' still present in display module"

    @pytest.mark.parametrize(
        "label",
        [
            "Imperial (°F)",
            "Metric (°C)",
            "Both (°F and °C)",
            "Auto (based on location)",
        ],
    )
    def test_new_labels_present_in_module(self, label):
        """New labels must appear in the display module source."""
        import inspect

        import accessiweather.ui.dialogs.settings_tabs.display as display_module

        source = inspect.getsource(display_module)
        assert label in source, f"New label '{label}' not found in display module"


class TestTempUnitBackwardCompatibility:
    """Internal config values must not change (backward compat with saved settings)."""

    def test_auto_value_unchanged(self):
        assert _TEMP_VALUES[0] == "auto"

    def test_imperial_maps_to_fahrenheit_value(self):
        # Index 1 is Imperial — must still save "f" to config
        assert _TEMP_VALUES[1] == "f"

    def test_metric_maps_to_celsius_value(self):
        # Index 2 is Metric — must still save "c" to config
        assert _TEMP_VALUES[2] == "c"

    def test_both_value_unchanged(self):
        assert _TEMP_VALUES[3] == "both"

    @pytest.mark.parametrize(
        "saved_value,expected_index",
        [
            ("auto", 0),
            ("f", 1),
            ("fahrenheit", 1),
            ("c", 2),
            ("celsius", 2),
            ("both", 3),
        ],
    )
    def test_temp_map_loads_correct_index(self, saved_value, expected_index):
        """Saved config values from old installations must load to the correct UI index."""
        assert _TEMP_MAP[saved_value] == expected_index

    def test_unknown_saved_value_defaults_gracefully(self):
        # Unknown values should not be in the map; callers use .get(val, default)
        assert _TEMP_MAP.get("unknown_unit", 3) == 3
