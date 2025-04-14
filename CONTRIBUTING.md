# Contributing to AccessiWeather

Thank you for your interest in contributing to AccessiWeather! This document provides guidelines and instructions for contributing to the beta release and beyond.

## Code of Conduct

Please be respectful and considerate when interacting with other contributors. We aim to foster an inclusive and welcoming community.

## Getting Started

1. Fork the repository
2. Clone your fork locally
3. Set up the development environment:
   ```
   pip install -e .
   ```
4. Create a new branch for your feature or bugfix:
   ```
   git checkout -b feature/your-feature-name
   ```

## Development Process

### Test-Driven Development

This project follows test-driven development (TDD) principles:

1. Write tests first that define the expected behavior
2. Run the tests to ensure they fail initially
3. Implement the feature to make the tests pass
4. Refactor your code while keeping tests passing
5. Commit your changes

### Running Tests

Use the provided script to run tests:

```
python run_tests.py
```

Or run pytest directly:

```
python -m pytest tests/
```

## Accessibility Requirements

All UI components must be accessible to screen readers. Before submitting a pull request that includes UI changes:

1. Ensure all UI elements have appropriate labels and descriptions
2. Test keyboard navigation for all new features
3. Verify that screen readers can properly announce UI elements
4. Follow the guidelines in the developer documentation

## Pull Request Process

1. Update the documentation to reflect any changes
2. Ensure all tests are passing
3. Update the version number if applicable
4. Submit a pull request with a clear description of your changes

## Style Guidelines

- Follow PEP 8 for Python code style with a 100 character line length
- Use Black for code formatting and isort for import sorting
- Run mypy for type checking
- Include docstrings for all modules, classes, and functions
- Use type hints where appropriate
- Include meaningful commit messages

You can check your code with:
```bash
python -m black src/accessiweather tests
python -m isort src/accessiweather tests
python -m flake8 src/accessiweather tests
python -m mypy src/accessiweather
```

## Feature Requests and Bug Reports

Please use the GitHub issue tracker to submit feature requests and bug reports. For bug reports, please include:

- A clear description of the issue
- Steps to reproduce
- Expected behavior
- Actual behavior
- Screenshots if applicable
- System information (OS, Python version, wxPython version)

## Beta Testing

During the beta phase, we especially appreciate feedback on:

1. Accessibility issues with screen readers
2. UI/UX improvements
3. Weather data accuracy and presentation
4. Performance on different systems
5. Installation and setup experience
