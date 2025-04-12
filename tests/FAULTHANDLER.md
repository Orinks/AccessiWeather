# Using Faulthandler in AccessiWeather Tests

This document explains how to use Python's faulthandler module to debug segmentation faults in the AccessiWeather application.

## Known Segmentation Fault Issues

The AccessiWeather application currently experiences segmentation faults during test execution, particularly when cleaning up wxPython objects. These segmentation faults typically occur:

1. After tests have successfully completed
2. During garbage collection of wxPython objects
3. When destroying wxPython windows and frames

We've implemented several mitigations in the test suite to reduce the likelihood of segmentation faults, but they may still occur. The segmentation faults don't affect the test results themselves, as they happen after the tests have completed.

## What is Faulthandler?

Faulthandler is a built-in Python module that helps debug segmentation faults and other serious crashes by displaying the Python traceback when a crash occurs. This is especially useful for debugging issues in C extensions like wxPython.

## How Faulthandler is Configured in AccessiWeather

In AccessiWeather, faulthandler is configured through a utility module:

```python
from accessiweather.utils.faulthandler_utils import enable_faulthandler, dump_traceback
```

The faulthandler is automatically enabled in `tests/conftest.py` for all tests, so you don't need to enable it manually in your test files.

## Faulthandler Log Files

Faulthandler logs are written to two locations:

1. **Console output**: Segmentation fault tracebacks are printed to stderr (the console)
2. **Log file**: Tracebacks are also saved to a log file:
   - For tests: `tests/logs/test_faulthandler.log`
   - For the main application: `~/AccessiWeather_logs/faulthandler.log`

## Manually Dumping Tracebacks

You can manually dump the current Python traceback at any point in your code:

```python
from accessiweather.utils.faulthandler_utils import dump_traceback

# Dump traceback for all threads
dump_traceback(all_threads=True)

# Dump traceback for current thread only
dump_traceback(all_threads=False)
```

This is useful for debugging deadlocks or investigating the state of threads at a specific point.

## Debugging Segmentation Faults

When a segmentation fault occurs:

1. Check the console output for the traceback
2. Check the appropriate log file for a more detailed traceback
3. Look for patterns in when the segmentation fault occurs:
   - Is it related to a specific wxPython component?
   - Does it happen during cleanup?
   - Is it related to thread interactions?

## Common Causes of Segmentation Faults in wxPython

1. **Accessing destroyed objects**: Trying to access a wxPython object after it has been destroyed
2. **Thread safety issues**: Updating UI from a non-main thread without using `wx.CallAfter`
3. **Event handling**: Improper event handling or event propagation
4. **Memory corruption**: Buffer overflows or other memory issues in C extensions
5. **Cleanup issues**: Improper cleanup of wxPython objects, especially during test teardown

## Best Practices

1. **Always use `wx.CallAfter`** when updating UI from a non-main thread
2. **Hide windows before destroying them** and use `wx.SafeYield()` after both operations
3. **Add delays** between critical operations to allow events to process
4. **Use proper teardown** in tests to clean up wxPython objects
5. **Check for segmentation faults** during both normal operation and cleanup
6. **Use pytest fixtures** instead of unittest for wxPython tests
7. **Set objects to None** after destroying them to help garbage collection
8. **Force garbage collection** after destroying wxPython objects
9. **Process events** before and after destroying objects with `wx.SafeYield()`

## Mitigations Implemented

We've implemented several mitigations to reduce segmentation faults:

1. **Improved cleanup in conftest.py**: Added more robust cleanup code with proper event processing and garbage collection
2. **Created wx_cleanup_utils.py**: Added utility functions for safely destroying wxPython objects
3. **Converted tests to use pytest fixtures**: This allows better control of the wxPython application lifecycle
4. **Added delays between operations**: This gives wxPython time to process events and clean up resources
5. **Enhanced faulthandler configuration**: Improved logging and signal handling for better diagnostics

## Running Tests with Extra Debugging

To run tests with extra debugging information:

```bash
python -m pytest tests/ -v --showlocals
```

For a specific test file:

```bash
python -m pytest tests/test_discussion_fetcher.py -v --showlocals
```