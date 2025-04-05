# AccessiWeather CI/CD Workflow

## Overview

This directory contains GitHub Actions workflows for the AccessiWeather project. The primary workflow (`python-app.yml`) is designed to run in a headless environment and handles testing of the wxPython-based GUI application without requiring an actual display.

## Workflow Details

### `python-app.yml`

This workflow runs on every push to the `main` branch and on pull requests targeting the `main` branch. It performs the following steps:

1. Sets up a Python 3.10 environment
2. Configures a virtual framebuffer (Xvfb) to simulate a display for wxPython
3. Installs all necessary dependencies
4. Runs the test suite with pytest and generates coverage reports
5. Uploads coverage data to Codecov (if configured)

## Headless Environment Considerations

The workflow uses Xvfb (X Virtual Framebuffer) to create a virtual display server, allowing wxPython to run its GUI components without an actual display. This is essential for running GUI tests in CI environments.

## Troubleshooting

If tests fail in the CI environment but pass locally, check for:

1. Tests that directly interact with GUI components without proper mocking
2. Tests that assume a specific screen resolution or display configuration
3. Tests that have timing issues (the CI environment may be slower)

Refer to the pre-commit hooks configuration for additional checks that help ensure tests are headless-friendly.
