# Testing AccessiWeather

This directory contains tests for the AccessiWeather application. The tests are designed to be robust, fast, and reliable, especially when dealing with wxPython's event-driven architecture.

## Testing Approach

We use a comprehensive testing approach that includes:

1. **Unit Tests**: Testing individual components in isolation
2. **Integration Tests**: Testing how components work together
3. **UI Tests**: Testing the user interface with proper event handling

## Test Utilities

The `gui_test_fixtures.py` module provides utilities and fixtures for testing wxPython applications:

### Utilities

- `wait_for`: Wait for a condition to be True or timeout
- `process_ui_events`: Process pending UI events
- `simulate_ui_action`: Simulate a UI action and process events
- `AsyncEventWaiter`: Wait for asynchronous events to complete

### Fixtures

- `mock_weather_app`: Create a WeatherApp instance with mocked services
- `nationwide_app`: Create a WeatherApp instance with mocked services for nationwide testing
- `ui_component_frame`: Create a frame for testing UI components
- `text_control`: Create an AccessibleTextCtrl for testing
- `list_control`: Create an AccessibleListCtrl for testing

## Test Fixtures

Common test fixtures are defined in `conftest.py`:

- `wx_app_session`: Session-scoped wx.App for testing
- `wx_app`: Function-scoped wx.App that uses the session app
- `temp_config_dir`: Temporary directory for configuration files
- `temp_config_file`: Temporary config file for testing
- `mock_api_client`: Mock NoaaApiClient with predefined responses
- `mock_notifier`: Mock WeatherNotifier
- `mock_location_manager`: Mock LocationManager with test data

## Best Practices

### Thread Safety

Always use `wx.CallAfter` or `wx.PostEvent` when updating the UI from a non-main thread:

```python
# Bad - may cause crashes or race conditions
def on_data_received(self, data):
    self.text_ctrl.SetValue(data)

# Good - thread-safe
def on_data_received(self, data):
    wx.CallAfter(self.text_ctrl.SetValue, data)
```

### Event Handling

Use `process_ui_events` to ensure UI updates are applied:

```python
def test_text_control_updates(text_control):
    # Set the value of the text control
    test_text = "This is a test of the text control"
    text_control.SetValue(test_text)

    # Process events to ensure UI updates are applied
    process_ui_events()

    # Verify the text control contains the expected content
    assert text_control.GetValue() == test_text
```

### Asynchronous Operations

Use `AsyncEventWaiter` for testing asynchronous operations:

```python
def test_nationwide_forecast_display(nationwide_app):
    app, _ = nationwide_app

    # Create an event waiter to track when the forecast is fetched
    waiter = AsyncEventWaiter()

    # Define the _on_forecast_fetched method to simulate the actual behavior
    def on_forecast_fetched(_, forecast_data):
        app.current_forecast = forecast_data
        formatted_text = app._format_national_forecast(forecast_data)
        app.forecast_text.SetValue(formatted_text)
        app._forecast_complete = True
        waiter.callback(formatted_text)

    # Bind the method to the app instance
    app._on_forecast_fetched = types.MethodType(on_forecast_fetched, app)

    # Call the method with test data
    test_data = app.weather_service.get_national_forecast_data.return_value
    app._on_forecast_fetched(test_data)

    # Wait for the forecast to be fetched and UI to update
    formatted_text = waiter.wait()
    assert formatted_text is not None, "Forecast fetch timed out"

    # Process events to ensure UI updates are applied
    process_ui_events()
```

### Using Real UI Components

Use real UI components when testing UI functionality to ensure the tests are realistic:

```python
@pytest.fixture
def text_control(ui_component_frame):
    # Create a real text control for testing
    text_ctrl = AccessibleTextCtrl(
        ui_component_frame,
        style=wx.TE_MULTILINE | wx.TE_READONLY,
        size=(400, 300),
        label="Test Text Control"
    )

    # Process events to ensure the control is properly initialized
    wx.Yield()

    yield text_ctrl
```

### Testing Accessibility

Always test that UI components are accessible to screen readers:

```python
def test_text_control_updates(text_control):
    # Set the value of the text control
    test_text = "This is a test of the text control"
    text_control.SetValue(test_text)

    # Process events to ensure UI updates are applied
    process_ui_events()

    # Verify the text control contains the expected content
    assert text_control.GetValue() == test_text

    # Verify that the text is accessible (has non-empty value)
    assert len(text_control.GetValue().strip()) > 0
```

## Running Tests

Run all tests:

```bash
python -m pytest tests/
```

Run specific tests:

```bash
python -m pytest tests/test_wx_async.py
```

Run tests with coverage:

```bash
python -m pytest tests/ --cov=src --cov-report=html
```
