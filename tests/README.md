# Testing AccessiWeather

This directory contains tests for the AccessiWeather application. The tests are designed to be robust, fast, and reliable, especially when dealing with wxPython's event-driven architecture.

## Testing Approach

We use a comprehensive testing approach that includes:

1. **Unit Tests**: Testing individual components in isolation
2. **Integration Tests**: Testing how components work together
3. **UI Tests**: Testing the user interface with proper event handling

## Test Utilities

The `wx_test_utils.py` module provides utilities for testing wxPython applications:

- `EventLoopContext`: Context manager for running code within a wx event loop
- `CallAfterContext`: Context manager for executing code with wx.CallAfter and waiting for completion
- `EventCatcher`: Catch and record wx events for testing
- `post_event`: Post an event to a window
- `wait_for_idle`: Wait for the application to be idle
- `simulate_user_input`: Simulate user input on a window
- `AsyncEventWaiter`: Wait for asynchronous events to complete

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

Use `EventCatcher` to test event handling:

```python
def test_button_click(self, wx_app):
    frame = MyFrame()
    catcher = EventCatcher([wx.EVT_BUTTON])
    catcher.bind_to_window(frame.my_button)
    
    # Post a button event
    post_event(frame.my_button, wx.EVT_BUTTON)
    
    # Wait for the event to be caught
    event = catcher.wait_for_event()
    assert event is not None
```

### Asynchronous Operations

Use `AsyncEventWaiter` for testing asynchronous operations:

```python
def test_async_operation(self, wx_app):
    frame = MyFrame()
    waiter = AsyncEventWaiter()
    
    # Patch the method to use our waiter
    original_method = frame.fetch_data
    def patched_method(*args, **kwargs):
        try:
            result = original_method(*args, **kwargs)
            waiter.callback(result)
        except Exception as e:
            waiter.error_callback(e)
        return result
    
    frame.fetch_data = patched_method
    
    # Trigger the operation
    wx.CallAfter(frame.fetch_data)
    
    # Wait for completion
    result = waiter.wait()
    assert result is not None
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
