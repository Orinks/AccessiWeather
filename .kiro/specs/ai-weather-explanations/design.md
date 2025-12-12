# Design Document

## Overview

This feature integrates OpenRouter's unified AI API into AccessiWeather to provide natural language explanations of weather conditions. The system uses OpenRouter's auto-routing capability to intelligently select appropriate AI models, supporting both free (no API key required) and paid tiers. The design prioritizes accessibility, cost control, and graceful error handling while maintaining AccessiWeather's existing architecture patterns.

The integration adds a new `AIExplainer` component that interfaces with OpenRouter's API, a settings UI for configuration, and UI elements for triggering and displaying explanations. All explanations are cached using the existing cache infrastructure to minimize API calls and costs.

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    AccessiWeatherApp                         │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              UI Layer (ui_builder.py)                 │   │
│  │  ┌────────────────┐      ┌──────────────────────┐   │   │
│  │  │ Weather Display│      │  Settings Dialog     │   │   │
│  │  │ + Explain Btn  │      │  + AI Config Section │   │   │
│  │  └────────┬───────┘      └──────────┬───────────┘   │   │
│  └───────────┼──────────────────────────┼───────────────┘   │
│              │                          │                    │
│  ┌───────────▼──────────────────────────▼───────────────┐   │
│  │           Business Logic Layer                        │   │
│  │  ┌──────────────────┐      ┌──────────────────────┐  │   │
│  │  │   AIExplainer    │◄─────┤  ConfigManager       │  │   │
│  │  │  (new module)    │      │  + AI settings       │  │   │
│  │  └────────┬─────────┘      └──────────────────────┘  │   │
│  │           │                                           │   │
│  │  ┌────────▼─────────┐      ┌──────────────────────┐  │   │
│  │  │  Cache Layer     │      │  WeatherClient       │  │   │
│  │  │  (cache.py)      │      │  (weather data)      │  │   │
│  │  └──────────────────┘      └──────────────────────┘  │   │
│  └───────────────────────────────────────────────────────┘   │
│              │                                                │
│  ┌───────────▼────────────────────────────────────────────┐  │
│  │              External APIs                              │  │
│  │  ┌──────────────────┐      ┌──────────────────────┐   │  │
│  │  │  OpenRouter API  │      │  Weather APIs        │   │  │
│  │  │  (AI models)     │      │  (NWS, Open-Meteo)   │   │  │
│  │  └──────────────────┘      └──────────────────────┘   │  │
│  └─────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Integration Points

1. **Configuration**: Extends `AppSettings` with AI-related fields
2. **UI**: Adds "Explain Weather" button to weather display and AI settings section
3. **Caching**: Reuses existing `cache.py` infrastructure for explanation caching
4. **Async**: Follows existing async patterns using `asyncio.to_thread()` for blocking API calls

## Components and Interfaces

### 1. AIExplainer Module (`src/accessiweather/ai_explainer.py`)

**Purpose**: Manages communication with OpenRouter API and generates weather explanations.

**Key Classes**:

```python
class AIExplainer:
    """Generates natural language weather explanations using OpenRouter."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "openrouter/auto:free",
        cache: Cache | None = None
    ):
        """Initialize with optional API key and model preference."""

    async def explain_weather(
        self,
        weather_data: dict[str, Any],
        location_name: str,
        style: ExplanationStyle = ExplanationStyle.STANDARD
    ) -> ExplanationResult:
        """Generate explanation for weather data.

        Args:
            weather_data: Current weather conditions dict
            location_name: Human-readable location name
            style: Explanation style (brief, standard, detailed)

        Returns:
            ExplanationResult with text, model used, and metadata

        Raises:
            AIExplainerError: Base exception for all AI-related errors
            InsufficientCreditsError: When account has no funds
            RateLimitError: When rate limits exceeded
            InvalidAPIKeyError: When API key is invalid
        """

    def _build_prompt(
        self,
        weather_data: dict[str, Any],
        location_name: str,
        style: ExplanationStyle
    ) -> str:
        """Construct prompt from weather data."""

    def _format_response(
        self,
        response_text: str,
        preserve_markdown: bool
    ) -> str:
        """Format AI response based on HTML rendering setting."""

    async def validate_api_key(self, api_key: str) -> bool:
        """Test if API key is valid by making a minimal API call."""


class ExplanationResult:
    """Result of an explanation generation."""
    text: str
    model_used: str
    token_count: int
    estimated_cost: float
    cached: bool
    timestamp: datetime


class ExplanationStyle(Enum):
    """Available explanation styles."""
    BRIEF = "brief"          # 1-2 sentences
    STANDARD = "standard"    # 3-4 sentences (default)
    DETAILED = "detailed"    # Full paragraph with context


# Custom exceptions
class AIExplainerError(Exception):
    """Base exception for AI explainer errors."""

class InsufficientCreditsError(AIExplainerError):
    """Raised when OpenRouter account has no funds."""

class RateLimitError(AIExplainerError):
    """Raised when rate limits are exceeded."""

class InvalidAPIKeyError(AIExplainerError):
    """Raised when API key is invalid or malformed."""
```

### 2. Configuration Extensions (`src/accessiweather/config/app_settings.py`)

**New Fields**:

```python
@dataclass
class AppSettings:
    # ... existing fields ...

    # AI Explanation Settings
    enable_ai_explanations: bool = False
    openrouter_api_key: str | None = None
    ai_model_preference: str = "auto:free"  # "auto:free", "auto", or specific model
    ai_explanation_style: str = "standard"  # "brief", "standard", "detailed"
    ai_cache_ttl: int = 300  # 5 minutes in seconds
```

### 3. UI Components

#### Explain Weather Button

Added to current weather display in `ui_builder.py`:

```python
def _build_weather_display(self) -> toga.Box:
    # ... existing weather display code ...

    if self.app.config_manager.get_config().settings.enable_ai_explanations:
        explain_button = toga.Button(
            "Explain Weather",
            on_press=self._on_explain_weather,
            aria_label="Get AI explanation of current weather",
            aria_description="Opens a dialog with natural language explanation of weather conditions"
        )
        weather_box.add(explain_button)
```

#### Explanation Dialog

New dialog class in `src/accessiweather/dialogs/explanation_dialog.py`:

```python
class ExplanationDialog:
    """Dialog for displaying AI-generated weather explanations."""

    def __init__(self, app: toga.App, explanation: ExplanationResult, location: str):
        """Create explanation dialog with result."""

    def show(self) -> None:
        """Display the dialog."""

    def _build_content(self) -> toga.Box:
        """Build dialog content with explanation text and metadata."""
```

#### AI Settings Section

Added to settings dialog in `src/accessiweather/dialogs/settings_dialog.py`:

```python
def _build_ai_settings_section(self) -> toga.Box:
    """Build AI explanation settings UI."""
    # Toggle: Enable AI Explanations
    # Input: OpenRouter API Key (password field)
    # Dropdown: Model Preference (Auto Free, Auto Paid, specific models)
    # Dropdown: Explanation Style (Brief, Standard, Detailed)
    # Button: Test API Key
    # Label: Usage info and pricing link
```

## Data Models

### Weather Context for AI

The weather data passed to the AI will be structured as follows:

```python
@dataclass
class WeatherContext:
    """Structured weather data for AI explanation."""
    location: str
    timestamp: datetime
    temperature: float
    temperature_unit: str
    conditions: str
    humidity: int | None
    wind_speed: float | None
    wind_direction: str | None
    visibility: float | None
    pressure: float | None
    alerts: list[dict[str, Any]]  # Active weather alerts
    forecast_summary: str | None  # Optional brief forecast

    def to_prompt_text(self) -> str:
        """Convert to natural language for AI prompt."""
```

### API Response Model

```python
@dataclass
class OpenRouterResponse:
    """Parsed response from OpenRouter API."""
    content: str
    model: str
    usage: dict[str, int]  # prompt_tokens, completion_tokens, total_tokens
    finish_reason: str

    @property
    def estimated_cost(self) -> float:
        """Calculate estimated cost based on model and tokens."""
```



## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*


### Property 1: Button visibility follows AI enablement setting
*For any* application state, when AI explanations are enabled in settings, the "Explain Weather" button should appear in the weather display, and when disabled, the button should not appear.
**Validates: Requirements 1.1, 1.5**

### Property 2: Model selection matches configuration
*For any* configuration state (no API key, API key with free models, API key with paid models), the system should use the correct model identifier: `openrouter/auto:free` for free models and `openrouter/auto` for paid models.
**Validates: Requirements 2.1, 2.2, 2.5**

### Property 3: Cache prevents duplicate API calls
*For any* weather data and explanation request, if a cached explanation exists and is less than 5 minutes old, the system should return the cached result without making a new API call.
**Validates: Requirements 2.4**

### Property 4: Settings persistence round-trip
*For any* valid AI configuration (API key, model preference, style), saving the settings and then loading them should produce equivalent configuration values.
**Validates: Requirements 3.5**

### Property 5: Prompt includes all required weather fields
*For any* weather data with temperature, conditions, humidity, wind speed, and visibility, the generated prompt should contain all these fields in a readable format.
**Validates: Requirements 4.1**

### Property 6: Alerts included when present
*For any* weather data, if active alerts exist, the generated prompt should include alert information; if no alerts exist, the prompt should not reference alerts.
**Validates: Requirements 4.2**

### Property 7: Markdown formatting follows HTML setting
*For any* AI response containing markdown, when HTML rendering is disabled, the formatted output should contain no markdown syntax; when HTML rendering is enabled, markdown should be preserved.
**Validates: Requirements 4.4, 4.5**

### Property 8: Most recent data source selected
*For any* set of weather data sources with different timestamps, the system should select the source with the most recent timestamp for explanation generation.
**Validates: Requirements 4.6**

### Property 9: Error messages are user-friendly
*For any* API error (network, authentication, rate limit, insufficient credits), the displayed error message should not contain technical details like stack traces, HTTP status codes, or raw API responses.
**Validates: Requirements 5.1**

### Property 10: Errors logged without user exposure
*For any* error condition, detailed error information (including stack traces and technical details) should be written to logs, but the user-facing message should only contain actionable information.
**Validates: Requirements 5.6**

### Property 11: Token counts displayed for paid models
*For any* explanation generated with paid models, the result should include token count information that is displayed to the user.
**Validates: Requirements 7.1**

### Property 12: Cost estimation precedes API calls
*For any* explanation request using paid models, the system should calculate an estimated cost before making the API call, not after.
**Validates: Requirements 7.3**

### Property 13: Session usage accumulates correctly
*For any* sequence of explanation generations in a session, the total usage count should equal the sum of individual explanation token counts.
**Validates: Requirements 7.4**

### Property 14: Free model cost display
*For any* explanation generated with free models (`:free` variant), the cost display should show "No cost" or equivalent zero-cost indicator.
**Validates: Requirements 7.5**

### Property 15: Accessibility attributes present
*For any* rendered "Explain Weather" button, the element should have both `aria-label` and `aria-description` attributes with non-empty values.
**Validates: Requirements 8.3**

### Property 16: Dialog focus management
*For any* explanation dialog that opens, the focus should be set to the explanation text element immediately after the dialog is displayed.
**Validates: Requirements 8.1**

### Property 17: Loading state announced
*For any* explanation request in progress, the UI should have an ARIA live region that announces the loading state to screen readers.
**Validates: Requirements 8.4**

### Property 18: Error announcements accessible
*For any* error that occurs during explanation generation, the error message should be announced via an ARIA live region with appropriate politeness level.
**Validates: Requirements 8.5**

## Error Handling

### Error Categories

1. **Network Errors**
   - Connection timeout
   - DNS resolution failure
   - No internet connectivity
   - User message: "Unable to connect to AI service. Check your internet connection."

2. **Authentication Errors**
   - Invalid API key format
   - Expired API key
   - Revoked API key
   - User message: "API key is invalid. Please check your settings."

3. **Authorization Errors**
   - Insufficient credits (no money on account)
   - User message: "Your OpenRouter account has no funds. Add credits or switch to free models in settings."

4. **Rate Limiting Errors**
   - Free tier rate limit exceeded
   - Paid tier rate limit exceeded
   - User message: "Rate limit exceeded. Try again in a few minutes or use a cached explanation."

5. **API Errors**
   - Model unavailable
   - Service degradation
   - Invalid request format
   - User message: "AI service temporarily unavailable. Try again later."

6. **Application Errors**
   - Invalid weather data format
   - Missing required fields
   - Cache corruption
   - User message: "Unable to generate explanation. Weather data may be incomplete."

### Error Handling Strategy

```python
async def explain_weather(self, weather_data: dict, location: str) -> ExplanationResult:
    """Generate explanation with comprehensive error handling."""
    try:
        # Check cache first
        cached = await self._get_cached_explanation(weather_data, location)
        if cached:
            return cached

        # Validate weather data
        self._validate_weather_data(weather_data)

        # Build prompt
        prompt = self._build_prompt(weather_data, location)

        # Make API call with timeout
        response = await asyncio.wait_for(
            self._call_openrouter(prompt),
            timeout=30.0
        )

        # Process and cache result
        result = self._process_response(response)
        await self._cache_explanation(weather_data, location, result)

        return result

    except asyncio.TimeoutError:
        logger.error("OpenRouter API timeout", exc_info=True)
        raise AIExplainerError("Request timed out. Try again later.")

    except InvalidAPIKeyError as e:
        logger.error(f"Invalid API key: {e}", exc_info=True)
        raise  # Re-raise with user-friendly message

    except InsufficientCreditsError as e:
        logger.error(f"Insufficient credits: {e}", exc_info=True)
        raise  # Re-raise with user-friendly message

    except RateLimitError as e:
        logger.error(f"Rate limit exceeded: {e}", exc_info=True)
        raise  # Re-raise with user-friendly message

    except requests.exceptions.ConnectionError as e:
        logger.error(f"Network connection error: {e}", exc_info=True)
        raise AIExplainerError("Unable to connect to AI service. Check your internet connection.")

    except Exception as e:
        logger.error(f"Unexpected error in AI explainer: {e}", exc_info=True)
        raise AIExplainerError("Unable to generate explanation. Try again later.")
```

### Fallback Behavior

When errors occur, the system provides graceful degradation:

1. **Cache Fallback**: If API call fails but cached explanation exists (even if stale), offer to show cached version
2. **Retry Logic**: For transient errors (network, timeout), allow user to retry with exponential backoff
3. **Feature Disable**: If persistent errors occur, suggest temporarily disabling AI features
4. **Alternative Actions**: Suggest viewing raw weather data or checking specific weather fields

## Testing Strategy

### Unit Testing

Unit tests will cover:

1. **AIExplainer Core Logic**
   - Prompt construction with various weather data combinations
   - Response formatting (markdown stripping vs preservation)
   - Model selection based on configuration
   - Cache key generation and lookup
   - Error message formatting

2. **Configuration Management**
   - Settings validation (API key format, model names)
   - Settings persistence and retrieval
   - Default value handling

3. **UI Components**
   - Button visibility based on settings
   - Dialog content structure
   - Accessibility attribute presence
   - Focus management

4. **Error Handling**
   - Each error type produces correct exception
   - User messages don't contain technical details
   - Logging captures full error context

### Property-Based Testing

Property-based tests will use the `hypothesis` library (already in AccessiWeather's test suite) to verify:

1. **Model Selection Property** (Property 2)
   - Generate random configuration states
   - Verify correct model identifier is used

2. **Cache Behavior Property** (Property 3)
   - Generate random weather data and timestamps
   - Verify cache hits/misses based on TTL

3. **Prompt Construction Property** (Property 5)
   - Generate random weather data with required fields
   - Verify all fields appear in prompt

4. **Markdown Formatting Property** (Property 7)
   - Generate random AI responses with markdown
   - Verify formatting matches HTML setting

5. **Data Source Selection Property** (Property 8)
   - Generate multiple data sources with random timestamps
   - Verify most recent is selected

6. **Error Message Property** (Property 9)
   - Generate various error conditions
   - Verify no technical details in user messages

7. **Usage Tracking Property** (Property 13)
   - Generate sequence of explanations
   - Verify total equals sum of parts

Each property test will run a minimum of 100 iterations to ensure coverage across the input space.

### Integration Testing

Integration tests (marked with `@pytest.mark.integration` to skip in CI) will:

1. **Real API Calls**
   - Test with actual OpenRouter API (using test API key)
   - Verify free model access works without key
   - Verify paid model access with valid key
   - Test rate limiting behavior

2. **End-to-End Flows**
   - Complete flow: enable feature → configure → generate explanation → display
   - Settings persistence across app restarts
   - Cache behavior with real TTL timing

3. **Error Scenarios**
   - Invalid API key handling
   - Network disconnection simulation
   - Rate limit exhaustion

### Test Configuration

```python
# conftest.py additions
@pytest.fixture
def mock_openrouter():
    """Mock OpenRouter API responses."""
    with patch('openai.OpenAI') as mock:
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Test explanation"))]
        mock_response.model = "openrouter/auto:free"
        mock_response.usage = {"total_tokens": 150, "prompt_tokens": 100, "completion_tokens": 50}
        mock_client.chat.completions.create.return_value = mock_response
        mock.return_value = mock_client
        yield mock_client

@pytest.fixture
def sample_weather_data():
    """Sample weather data for testing."""
    return {
        "temperature": 72.5,
        "temperature_unit": "F",
        "conditions": "Partly Cloudy",
        "humidity": 65,
        "wind_speed": 8.5,
        "wind_direction": "NW",
        "visibility": 10.0,
        "pressure": 29.92,
        "alerts": []
    }
```

### Test Markers

- `@pytest.mark.unit` - Fast, isolated tests (run in CI)
- `@pytest.mark.integration` - Tests with real API calls (skipped in CI)
- `@pytest.mark.property` - Property-based tests using Hypothesis
- `@pytest.mark.accessibility` - Tests for ARIA and accessibility features

## Implementation Notes

### Dependencies

Add to `pyproject.toml`:

```toml
[project]
dependencies = [
    # ... existing dependencies ...
    "openai>=1.0.0",  # OpenAI SDK (OpenRouter compatible)
]
```

### API Key Security

- Store API key in config file (already encrypted at rest by OS)
- Never log API key values
- Mask API key in UI (show only last 4 characters)
- Validate format before storage (starts with "sk-or-")

### Performance Considerations

1. **Async Operations**: All API calls use `asyncio.to_thread()` to avoid blocking UI
2. **Timeouts**: 30-second timeout on API calls to prevent hanging
3. **Caching**: 5-minute TTL reduces API calls by ~90% for repeated views
4. **Lazy Loading**: AIExplainer only initialized when feature is enabled

### Accessibility Requirements

All UI elements must include:
- `aria-label`: Brief description of element purpose
- `aria-description`: Detailed explanation of what happens on interaction
- `role`: Semantic role for screen readers
- Focus management: Dialogs trap focus, buttons are keyboard accessible
- ARIA live regions: Loading states and errors announced automatically

### Cost Optimization

1. **Default to Free**: New users start with `openrouter/auto:free`
2. **Cache Aggressively**: 5-minute TTL prevents duplicate calls
3. **Prompt Optimization**: Keep prompts concise (~200 tokens)
4. **Token Limits**: Set max_tokens=200 for responses to control costs
5. **Usage Tracking**: Show users their approximate spending

### Future Enhancements

Potential future additions (not in current scope):

1. **Explanation History**: Save past explanations for offline viewing
2. **Custom Prompts**: Let users customize explanation style/tone
3. **Multi-Language**: Generate explanations in user's preferred language
4. **Voice Output**: Integrate with text-to-speech for audio explanations
5. **Comparison Mode**: Explain differences between forecast and actual weather
6. **Alert Summaries**: Dedicated AI summaries of weather alerts
