# Design Document

## Overview

This feature extends the AI weather explanation system to allow users to customize the prompts sent to AI models. Users can modify the system prompt (which defines the AI's personality and response style) and add custom instructions that are appended to each request. The design integrates with the existing `AIExplainer` module and configuration system, adding new settings fields and UI components while maintaining backward compatibility with the default prompts.

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    AccessiWeatherApp                         │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              UI Layer                                 │   │
│  │  ┌────────────────────────────────────────────────┐  │   │
│  │  │  Settings Dialog                               │  │   │
│  │  │  └── AI Settings Section                       │  │   │
│  │  │      └── Prompt Customization Panel (NEW)      │  │   │
│  │  │          ├── System Prompt Editor              │  │   │
│  │  │          ├── Custom Instructions Editor        │  │   │
│  │  │          ├── Reset Buttons                     │  │   │
│  │  │          └── Preview Button                    │  │   │
│  │  └────────────────────────────────────────────────┘  │   │
│  └───────────────────────────────────────────────────────┘   │
│              │                                                │
│  ┌───────────▼────────────────────────────────────────────┐  │
│  │           Business Logic Layer                          │  │
│  │  ┌──────────────────┐      ┌──────────────────────┐    │  │
│  │  │   AIExplainer    │◄─────┤  ConfigManager       │    │  │
│  │  │  (modified)      │      │  + prompt settings   │    │  │
│  │  │  - uses custom   │      └──────────────────────┘    │  │
│  │  │    prompts       │                                   │  │
│  │  └──────────────────┘                                   │  │
│  └─────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Integration Points

1. **Configuration**: Extends `AppSettings` with prompt customization fields
2. **AIExplainer**: Modified to use custom prompts when configured
3. **Settings UI**: New prompt customization panel in AI settings section

## Components and Interfaces

### 1. Configuration Extensions (`src/accessiweather/config/app_settings.py`)

**New Fields**:

```python
@dataclass
class AppSettings:
    # ... existing fields ...

    # Prompt Customization Settings (NEW)
    custom_system_prompt: str | None = None  # None means use default
    custom_instructions: str | None = None   # Appended to user prompt
```

### 2. AIExplainer Modifications (`src/accessiweather/ai_explainer.py`)

**New Methods and Changes**:

```python
class AIExplainer:
    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_FREE_MODEL,
        cache: Cache | None = None,
        custom_system_prompt: str | None = None,  # NEW
        custom_instructions: str | None = None,   # NEW
    ):
        # ... existing init ...
        self.custom_system_prompt = custom_system_prompt
        self.custom_instructions = custom_instructions

    def get_effective_system_prompt(self, style: ExplanationStyle) -> str:
        """Get the system prompt to use, preferring custom over default."""
        if self.custom_system_prompt:
            return self.custom_system_prompt
        return self._build_default_system_prompt(style)

    def _build_default_system_prompt(self, style: ExplanationStyle) -> str:
        """Build the default system prompt (existing _build_system_prompt logic)."""
        # Renamed from _build_system_prompt for clarity
        ...

    def _build_prompt(
        self,
        weather_data: dict[str, Any],
        location_name: str,
        style: ExplanationStyle,
    ) -> str:
        """Construct prompt from weather data, including custom instructions."""
        # ... existing prompt building ...

        # Append custom instructions if configured
        if self.custom_instructions:
            prompt_parts.append(f"\n\nAdditional Instructions: {self.custom_instructions}")

        return "".join(prompt_parts)

    def get_prompt_preview(
        self,
        style: ExplanationStyle = ExplanationStyle.STANDARD,
    ) -> dict[str, str]:
        """Generate a preview of the prompts that will be sent to the AI."""
        sample_weather = {
            "temperature": 72,
            "temperature_unit": "F",
            "conditions": "Partly Cloudy",
            "humidity": 65,
            "wind_speed": 8,
            "wind_direction": "NW",
        }
        return {
            "system_prompt": self.get_effective_system_prompt(style),
            "user_prompt": self._build_prompt(sample_weather, "Sample Location", style),
        }

    @staticmethod
    def get_default_system_prompt() -> str:
        """Return the default system prompt text for display in UI."""
        return (
            "You are a helpful weather assistant that explains weather conditions "
            "in plain, accessible language. Your explanations should be easy to "
            "understand for screen reader users and people who prefer audio descriptions. "
            "Avoid using visual-only descriptions. Focus on how the weather will feel "
            "and what activities it's suitable for."
        )
```

### 3. UI Components

#### Prompt Customization Panel

Added to settings dialog in `src/accessiweather/dialogs/settings_dialog.py`:

```python
def _build_prompt_customization_section(self) -> toga.Box:
    """Build prompt customization UI."""
    # MultilineTextInput: Custom System Prompt
    # - Placeholder shows default prompt
    # - aria-label and aria-description for accessibility

    # MultilineTextInput: Custom Instructions
    # - Placeholder explains purpose
    # - aria-label and aria-description for accessibility

    # Button: Reset System Prompt to Default
    # Button: Reset Instructions
    # Button: Preview Prompt
```

## Data Models

### Prompt Configuration

```python
@dataclass
class PromptConfig:
    """Configuration for AI prompts."""
    custom_system_prompt: str | None = None
    custom_instructions: str | None = None

    def is_using_defaults(self) -> bool:
        """Check if using all default prompts."""
        return self.custom_system_prompt is None and self.custom_instructions is None
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Custom system prompt used when configured
*For any* non-empty custom system prompt string, when building an AI request, the effective system prompt should equal the custom value, not the default.
**Validates: Requirements 1.2**

### Property 2: Default prompt used when custom is empty
*For any* configuration state where custom_system_prompt is None or empty string, the effective system prompt should equal the built-in default prompt.
**Validates: Requirements 1.3**

### Property 3: Configuration persistence round-trip
*For any* valid prompt configuration (custom system prompt and custom instructions), saving to configuration and then loading should produce equivalent values.
**Validates: Requirements 1.4, 2.4**

### Property 4: Custom instructions appended to prompt
*For any* non-empty custom instructions string, the generated user prompt should contain the custom instructions text.
**Validates: Requirements 2.1**

### Property 5: Custom instructions positioned after weather data
*For any* prompt with custom instructions, the instructions should appear after the weather data section in the user prompt.
**Validates: Requirements 2.2**

### Property 6: Empty instructions not included
*For any* configuration with empty or None custom instructions, the generated user prompt should not contain an "Additional Instructions" section.
**Validates: Requirements 2.3**

### Property 7: Reset restores defaults
*For any* configuration state, after calling reset for system prompt, the effective system prompt should equal the default; after calling reset for instructions, custom instructions should be None.
**Validates: Requirements 3.1, 3.2, 3.3**

### Property 8: Preview includes custom instructions
*For any* configuration with custom instructions, the preview output should include those instructions in the user prompt section.
**Validates: Requirements 4.3**

### Property 9: Accessibility attributes present
*For any* rendered prompt customization form element (text inputs, buttons), the element should have both `aria-label` and `aria-description` attributes with non-empty values.
**Validates: Requirements 5.1, 5.2**

## Error Handling

### Validation

1. **Prompt Length**: Custom prompts are validated for reasonable length (max 2000 characters for system prompt, max 500 for instructions)
2. **Character Validation**: Prompts are sanitized to remove control characters that could cause issues

### Error Messages

- "System prompt is too long (max 2000 characters)" - when exceeding length limit
- "Custom instructions are too long (max 500 characters)" - when exceeding length limit
- "Prompt reset to default" - confirmation after reset

## Testing Strategy

### Unit Testing

Unit tests will cover:

1. **Prompt Construction**
   - Custom system prompt is used when configured
   - Default prompt is used when custom is empty/None
   - Custom instructions are appended correctly
   - Instructions appear after weather data

2. **Configuration**
   - Prompt settings are saved correctly
   - Prompt settings are loaded correctly
   - Reset clears custom values

3. **Preview Generation**
   - Preview includes system prompt
   - Preview includes sample user prompt
   - Preview includes custom instructions when configured

### Property-Based Testing

Property-based tests will use the `hypothesis` library to verify:

1. **Custom Prompt Usage** (Property 1, 2)
   - Generate random custom prompts
   - Verify correct prompt is used based on configuration

2. **Configuration Round-Trip** (Property 3)
   - Generate random prompt configurations
   - Verify save/load produces equivalent values

3. **Instructions Inclusion** (Property 4, 5, 6)
   - Generate random instructions
   - Verify correct inclusion/exclusion in prompts

4. **Reset Behavior** (Property 7)
   - Generate random configurations
   - Verify reset restores defaults

Each property test will run a minimum of 100 iterations.

### Test Configuration

```python
@pytest.fixture
def ai_explainer_with_custom_prompts():
    """AIExplainer with custom prompt configuration."""
    return AIExplainer(
        api_key="test-key",
        custom_system_prompt="You are a friendly weather bot.",
        custom_instructions="Keep responses under 50 words.",
    )

@pytest.fixture
def sample_weather_data():
    """Sample weather data for testing."""
    return {
        "temperature": 72,
        "temperature_unit": "F",
        "conditions": "Sunny",
        "humidity": 45,
    }
```

</content>
</invoke>
