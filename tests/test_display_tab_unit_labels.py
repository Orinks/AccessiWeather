"""Tests for issue #558 — temperature unit preference labels are Auto/Imperial/Metric."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from accessiweather.ui.dialogs.settings_tabs import display as display_module
from accessiweather.ui.dialogs.settings_tabs.display import _TEMP_MAP, _TEMP_VALUES, DisplayTab


class TestTempUnitChoiceLabels:
    """The UI choices must use the new Auto/Imperial/Metric naming convention."""

    def test_temperature_unit_choices_use_public_labels(self, monkeypatch):
        """Temperature unit choices should be asserted through the constructed UI."""
        expected_labels = [
            "Auto (based on location)",
            "Imperial (°F)",
            "Metric (°C)",
            "Both (°F and °C)",
        ]

        monkeypatch.setattr(
            display_module.wx,
            "ScrolledWindow",
            MagicMock(return_value=MagicMock()),
            raising=False,
        )
        monkeypatch.setattr(
            display_module.wx,
            "SpinCtrl",
            MagicMock(return_value=MagicMock()),
            raising=False,
        )
        monkeypatch.setattr(display_module.wx, "ALIGN_CENTER_VERTICAL", 0, raising=False)
        monkeypatch.setattr(display_module.wx, "Choice", MagicMock(return_value=MagicMock()))

        dialog = MagicMock()
        dialog._controls = {}
        dialog.create_section.return_value = MagicMock()

        def add_labeled_control_row(_panel, _sizer, label, control_factory, **_kwargs):
            control = control_factory(_panel)
            dialog._controls[label] = control
            return control

        dialog.add_labeled_control_row.side_effect = add_labeled_control_row

        DisplayTab(dialog).create()

        temperature_choice_call = display_module.wx.Choice.call_args_list[0]
        assert temperature_choice_call.kwargs["choices"] == expected_labels

    def test_temperature_unit_values_preserve_saved_config_contract(self):
        assert _TEMP_VALUES == ["auto", "f", "c", "both"]


class TestTempUnitBackwardCompatibility:
    """Internal config values must not change (backward compat with saved settings)."""

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
