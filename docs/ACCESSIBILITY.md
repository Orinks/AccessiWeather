# AccessiWeather Accessibility Guidelines

## Overview

AccessiWeather is designed with accessibility as a core priority, ensuring full functionality for screen reader users and keyboard navigation. This document outlines the accessibility standards and patterns used throughout the application.

## Core Principles

1. **Screen Reader Compatibility**: All interactive UI elements must have proper ARIA attributes
2. **Keyboard Navigation**: All functionality must be accessible via keyboard (Tab/Shift+Tab navigation)
3. **Clear Labels**: Every control must have both a short label and detailed description
4. **Logical Flow**: UI elements must be ordered in a way that makes sense when navigating linearly

## ARIA Attribute Requirements

### Required Attributes

All Toga widgets with user interaction must have:

- **`aria_label`**: Short, concise description (< 50 characters)
  - Used by screen readers as the primary identifier
  - Should be clear and unambiguous
  - Example: `"Toggle weather alerts"`

- **`aria_description`**: Detailed explanation (> 20 characters)
  - Provides context about the widget's purpose and behavior
  - Explains what the control does and what values are valid
  - Example: `"Master control to enable or disable all weather alert functionality."`

### Widget-Specific Guidelines

#### Switches (Toggle Controls)

```python
enable_alerts_switch = toga.Switch(
    "Enable weather alerts",  # Visible on-screen text
    value=True,
    id="enable_alerts_switch"
)
enable_alerts_switch.aria_label = "Toggle weather alerts"
enable_alerts_switch.aria_description = (
    "Master control to enable or disable all weather alert functionality."
)
```

**Guidelines:**
- `aria_label`: Start with "Toggle" to indicate it's a switch
- `aria_description`: Explain what the switch controls and the impact of changing it

#### NumberInput Widgets

```python
alert_global_cooldown_input = toga.NumberInput(
    value=5,
    min=0,
    max=60,
    id="alert_global_cooldown_input"
)
alert_global_cooldown_input.aria_label = "Global notification cooldown"
alert_global_cooldown_input.aria_description = (
    "Set the minimum number of minutes to wait between any alert notifications, "
    "from 0 to 60 minutes. This prevents notification spam across all alerts."
)
```

**Guidelines:**
- `aria_label`: Short description of the value being set
- `aria_description`: Include valid range (min to max) and explain the purpose

#### Selection Dropdowns

```python
update_channel_selection = toga.Selection(
    items=["Stable", "Beta", "Development"],
    id="update_channel_selection"
)
update_channel_selection.aria_label = "Update channel selection"
update_channel_selection.aria_description = (
    "Choose which release channel to follow for application updates."
)
```

**Guidelines:**
- `aria_label`: End with "selection" to indicate it's a dropdown
- `aria_description`: Explain what the selection controls

## Keyboard Navigation

### Navigation Order

Widgets are added to containers in the order they should be navigated:

1. **Master Controls**: Primary enable/disable switches
2. **Configuration Options**: Detailed settings in logical groups
3. **Action Buttons**: OK, Cancel, Apply buttons

### Focus Management

```python
# Set initial focus on the most important widget
dialog.primary_widget.focus()
```

**Guidelines:**
- Set initial focus on the most relevant widget for the user's task
- `.focus()` may fail silently on some platforms - use try/except if critical

## Alert Notification UI Examples

### Notifications Tab Structure

The alert notifications settings tab follows this structure:

1. **Master Controls** (top)
   - Enable weather alerts switch
   - Enable alert notifications switch

2. **Severity Level Filters** (middle)
   - Extreme severity switch
   - Severe severity switch
   - Moderate severity switch
   - Minor severity switch
   - Unknown severity switch

3. **Rate Limiting Settings** (bottom)
   - Global cooldown input (0-60 minutes)
   - Per-alert cooldown input (0-1440 minutes)
   - Max notifications per hour input (1-100)

### Complete Example

```python
# Master control switch with full accessibility
dialog.enable_alerts_switch = toga.Switch(
    "Enable weather alerts",
    value=dialog.current_settings.enable_alerts,
    style=Pack(margin_bottom=10),
    id="enable_alerts_switch",
)
dialog.enable_alerts_switch.aria_label = "Toggle weather alerts"
dialog.enable_alerts_switch.aria_description = (
    "Master control to enable or disable all weather alert functionality."
)
notifications_box.add(dialog.enable_alerts_switch)

# Rate limiting number input with full accessibility
dialog.alert_global_cooldown_input = toga.NumberInput(
    value=getattr(dialog.current_settings, "alert_global_cooldown_minutes", 5),
    min=0,
    max=60,
    style=Pack(margin_bottom=12),
    id="alert_global_cooldown_input",
)
dialog.alert_global_cooldown_input.aria_label = "Global notification cooldown"
dialog.alert_global_cooldown_input.aria_description = (
    "Set the minimum number of minutes to wait between any alert notifications, "
    "from 0 to 60 minutes. This prevents notification spam across all alerts."
)
notifications_box.add(dialog.alert_global_cooldown_input)
```

## Testing Accessibility

### Unit Tests with toga_dummy

All accessibility features must be tested:

```python
import os
import toga
from unittest.mock import MagicMock

@pytest.fixture
def mock_app():
    """Create a mock Toga app instance with dummy backend."""
    os.environ["TOGA_BACKEND"] = "toga_dummy"
    app = toga.App("Test AccessiWeather", "org.beeware.test")
    app.config = MagicMock()
    app.on_exit = lambda: True
    yield app

def test_switch_has_aria_attributes(mock_app, mock_config_manager):
    """Verify switches have proper aria attributes."""
    dialog = SettingsDialog(app=mock_app, config_manager=mock_config_manager)
    dialog.show_and_prepare()  # Initialize UI widgets

    # Check aria_label exists and is concise
    assert dialog.enable_alerts_switch.aria_label == "Toggle weather alerts"
    assert len(dialog.enable_alerts_switch.aria_label) < 50

    # Check aria_description provides context
    assert "master control" in dialog.enable_alerts_switch.aria_description.lower()
    assert len(dialog.enable_alerts_switch.aria_description) > 20
```

### Test Coverage Requirements

For each interactive widget, tests must verify:

1. Widget exists and is not None
2. `aria_label` is present and concise (< 50 characters)
3. `aria_description` is present and informative (> 20 characters)
4. Descriptions contain key context words
5. NumberInput widgets have proper `min`/`max` constraints

## Screen Reader Compatibility

### Supported Screen Readers

- **Windows**: NVDA, JAWS
- **macOS**: VoiceOver
- **Linux**: Orca

### Testing with Screen Readers

Manual testing checklist:

1. Navigate to settings dialog
2. Tab through all alert widgets
3. Verify each widget announces:
   - Widget type (switch, number input, dropdown)
   - Current value
   - aria_label
   - aria_description
4. Verify keyboard shortcuts work (Space to toggle, Arrow keys for inputs)

## Common Pitfalls

### ❌ Missing ARIA Attributes

```python
# BAD: No aria attributes
cooldown_input = toga.NumberInput(value=5, min=0, max=60)
notifications_box.add(cooldown_input)
```

### ✅ Complete ARIA Attributes

```python
# GOOD: Full aria attributes
cooldown_input = toga.NumberInput(value=5, min=0, max=60, id="cooldown_input")
cooldown_input.aria_label = "Global notification cooldown"
cooldown_input.aria_description = (
    "Set the minimum number of minutes to wait between any alert notifications, "
    "from 0 to 60 minutes. This prevents notification spam across all alerts."
)
notifications_box.add(cooldown_input)
```

### ❌ Vague Descriptions

```python
# BAD: Too vague
switch.aria_description = "Turns on alerts"
```

### ✅ Detailed Descriptions

```python
# GOOD: Clear and informative
switch.aria_description = (
    "Master control to enable or disable all weather alert functionality."
)
```

## Maintenance Guidelines

### Adding New Widgets

When adding any new interactive widget:

1. Add `id` parameter for automated testing
2. Set `aria_label` (short, < 50 chars)
3. Set `aria_description` (detailed, > 20 chars)
4. Add to appropriate container in logical navigation order
5. Write unit tests verifying aria attributes

### Code Review Checklist

Before merging UI changes:

- [ ] All interactive widgets have `aria_label`
- [ ] All interactive widgets have `aria_description`
- [ ] Labels are concise (< 50 characters)
- [ ] Descriptions are informative (> 20 characters)
- [ ] Navigation order is logical
- [ ] Unit tests verify aria attributes
- [ ] Manual screen reader testing completed

## References

- [Toga Accessibility Documentation](https://toga.readthedocs.io/en/stable/reference/api/widgets/base.html#toga.Widget.aria_label)
- [WCAG 2.1 Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)
- [ARIA Best Practices](https://www.w3.org/WAI/ARIA/apg/)
- [BeeWare Accessibility](https://beeware.org/contributing/accessibility/)

## Contact

For accessibility questions or issues:
- Open a GitHub issue with the `accessibility` label
- Tag @accessibility-team in pull requests
