"""Accessible UI components for AccessiWeather

This module provides accessible UI widgets that enhance screen reader support.
It re-exports components from the basic_components, list_components, and
autocomplete_components modules.
"""

# Re-export components from autocomplete_components
from .autocomplete_components import AccessibleComboBox

# Re-export components from basic_components
from .basic_components import (
    AccessibleButton,
    AccessibleChoice,
    AccessibleStaticText,
    AccessibleTextCtrl,
)

# Re-export components from list_components
from .list_components import AccessibleListCtrl

# Define __all__ to explicitly export symbols
__all__ = [
    "AccessibleButton",
    "AccessibleChoice",
    "AccessibleStaticText",
    "AccessibleTextCtrl",
    "AccessibleListCtrl",
    "AccessibleComboBox",
]
