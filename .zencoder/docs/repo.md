# AccessiWeather Information

## Summary
AccessiWeather is an accessible weather application that provides current conditions, forecasts, and weather alerts with a focus on screen reader compatibility. It supports both NOAA and Open-Meteo weather data sources.

## Structure
- `src/accessiweather`: Main application source code
- `tests`: Test suite for the application
- `docs`: Project documentation
- `installer`: Installation scripts and configurations
- `scripts`: Utility scripts for development and testing

## Language & Runtime
**Language**: Python
**Version**: Requires Python 3.7+ (Python 3.11 recommended)
**Build System**: setuptools
**Package Manager**: pip

## Dependencies
**Main Dependencies**:
- toga (GUI framework)
- httpx (HTTP client)
- desktop-notifier
- geopy (Geocoding)
- python-dateutil
- beautifulsoup4
- attrs
- psutil

**Development Dependencies**:
- pytest, pytest-mock, pytest-cov (Testing)
- types-requests (Type hints)
- PyInstaller (Packaging)

## Build & Installation

### Environment Setup
Before running any commands, check for existing virtual environments:

```bash
# Check for common virtual environment directories
if [ -d ".venv" ]; then
    echo "Using existing virtual environment (.venv)"
    source .venv/bin/activate  # On Linux/macOS
    # OR
    # .venv\Scripts\activate  # On Windows
elif [ -d "venv" ]; then
    echo "Using existing virtual environment (venv)"
    source venv/bin/activate  # On Linux/macOS
    # OR
    # venv\Scripts\activate  # On Windows
elif [ -d "env" ]; then
    echo "Using existing virtual environment (env)"
    source env/bin/activate  # On Linux/macOS
    # OR
    # env\Scripts\activate  # On Windows
else
    echo "Creating new virtual environment"
    python -m venv .venv
    source .venv/bin/activate  # On Linux/macOS
    # OR
    # .venv\Scripts\activate  # On Windows
fi
```

For Windows PowerShell:
```powershell
# Check for common virtual environment directories
if (Test-Path ".venv") {
    Write-Host "Using existing virtual environment (.venv)"
    .\.venv\Scripts\Activate.ps1
}
elseif (Test-Path "venv") {
    Write-Host "Using existing virtual environment (venv)"
    .\venv\Scripts\Activate.ps1
}
elseif (Test-Path "env") {
    Write-Host "Using existing virtual environment (env)"
    .\env\Scripts\Activate.ps1
}
else {
    Write-Host "Creating new virtual environment"
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
}
```

### Installation
```bash
# Install the package in development mode
pip install -e .

# Install development dependencies
pip install -e ".[dev]"
```

## Testing
**Framework**: pytest
**Test Location**: `tests/` directory
**Configuration**: `pytest.ini`, `tox.ini`
**Run Command**:
```bash
# Check for existing virtual environment before running tests
if [ -d ".venv" ] && [ -f ".venv/bin/pytest" ]; then
    .venv/bin/pytest
elif [ -d "venv" ] && [ -f "venv/bin/pytest" ]; then
    venv/bin/pytest
elif [ -d "env" ] && [ -f "env/bin/pytest" ]; then
    env/bin/pytest
else
    pytest
fi
```

For Windows:
```powershell
# Check for existing virtual environment before running tests
if (Test-Path ".venv\Scripts\pytest.exe") {
    .\.venv\Scripts\pytest
}
elseif (Test-Path "venv\Scripts\pytest.exe") {
    .\venv\Scripts\pytest
}
elseif (Test-Path "env\Scripts\pytest.exe") {
    .\env\Scripts\pytest
}
else {
    pytest
}
```