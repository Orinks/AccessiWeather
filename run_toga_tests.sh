#!/bin/bash
# Script to run only Toga-specific tests

export TOGA_BACKEND=toga_dummy

# Run only the Toga tests we created
python -m pytest tests/test_simple_app.py::TestAccessiWeatherAppAsyncOperations -v --tb=short
