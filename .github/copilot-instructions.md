# AccessiWeather Development Instructions

**ALWAYS follow these instructions first and ONLY fallback to additional search and context gathering if the information in these instructions is incomplete or found to be in error.**

AccessiWeather is a Python 3.7+ desktop weather application built with wxPython, featuring comprehensive accessibility support and international weather data. It uses PyInstaller for building Windows executables and has a complete CI/CD pipeline.

## Working Effectively

### Bootstrap, Build, and Test the Repository

1. **Install Python dependencies (NETWORKING REQUIRED)**:
   ```bash
   python -m pip install --upgrade pip --timeout=600
   pip install -e .[dev] --timeout=600
   ```
   - **TIMING**: Dependency installation takes 5-30 minutes depending on network. NEVER CANCEL.
   - **KNOWN ISSUE**: wxPython installation may fail due to network timeouts or firewall limitations.
   - **WORKAROUND**: Install core dependencies individually if needed:
     ```bash
     pip install --timeout=600 requests plyer geopy python-dateutil beautifulsoup4 httpx attrs psutil
     pip install --timeout=600 pytest pytest-mock pytest-cov requests-mock PyInstaller
     ```

2. **Install development tools**:
   ```bash
   pip install --timeout=600 pre-commit black isort flake8 mypy bandit safety
   ```
   - **TIMING**: Takes 2-10 minutes. NEVER CANCEL - Set timeout to 15+ minutes.

3. **Build executable with PyInstaller**:
   ```bash
   # Basic build test (without wxPython)
   python -m PyInstaller --help
   
   # Full build (requires wxPython)
   ./installer/build_installer.sh  # Linux/Unix
   # OR
   ./installer/build_installer.ps1  # Windows PowerShell
   ```
   - **TIMING**: Full build takes 5-15 minutes. NEVER CANCEL - Set timeout to 30+ minutes.

4. **Run tests**:
   ```bash
   # Unit tests (fast, excluding GUI components due to wxPython dependency)
   python -m pytest -m "unit" -v --tb=short --maxfail=5
   
   # Integration tests (requires full environment)
   python -m pytest tests/test_integration_comprehensive.py -v --tb=short
   
   # Local CI simulation
   python test_ci_locally.py
   ```
   - **TIMING**: Unit tests take 30 seconds-2 minutes. Integration tests take 2-5 minutes. NEVER CANCEL.
   - **CRITICAL**: Tests require wxPython. Many tests will fail without it due to GUI dependencies.

## Build Process Details

### Core Commands (VALIDATED)
- **Python environment check**: `python --version` (instant)
- **Dependency installation**: `pip install -e .[dev]` (5-30 minutes, timeout=1800)
- **Non-GUI component test**: Core utilities work without wxPython
- **PyInstaller availability**: `python -m PyInstaller --version` (instant)

### Build Timing Expectations (MEASURED)
- **pip install basic dependencies**: 2-5 minutes (validated)
- **pip install with wxPython**: 10-30 minutes (often fails due to network timeouts)
- **PyInstaller simple script**: 7-8 seconds (validated with test script)
- **PyInstaller full app**: 5-15 minutes for complete application (estimated based on complexity)
- **Test suite basic**: 30 seconds-2 minutes (for non-GUI components)
- **Test suite full**: 2-5 minutes (requires wxPython for GUI tests)
- **CI pipeline**: 15-30 minutes total (based on GitHub Actions configuration)

### NEVER CANCEL Operations
- **ANY pip install command** - Always use timeouts of 600+ seconds
- **PyInstaller builds** - Always use timeouts of 1800+ seconds  
- **Test execution** - Always use timeouts of 300+ seconds

## Application Structure

### Core Components (Work Without wxPython)
- **Temperature utilities**: `src/accessiweather/utils/temperature_utils.py`
- **Configuration**: `src/accessiweather/config_utils.py`
- **Constants**: `src/accessiweather/constants.py`
- **API clients**: `src/accessiweather/openmeteo_client.py`, `src/accessiweather/api_client.py`

### GUI Components (Require wxPython)
- **Main application**: `src/accessiweather/main.py`
- **Settings dialog**: `src/accessiweather/gui/settings_dialog.py`
- **Alert dialogs**: `src/accessiweather/gui/alert_dialog.py`

### Test Structure
- **Unit tests**: Tests marked with `@pytest.mark.unit`
- **Integration tests**: `tests/test_integration_*.py`
- **GUI tests**: `tests/test_*_gui.py` 
- **Performance tests**: `tests/test_integration_performance.py`

## Validation Scenarios

### Repository Health Check (ALWAYS run first)
```bash
# Quick structure validation
python -c "
import os
key_dirs = ['src/accessiweather', 'tests', 'installer', '.github/workflows']
key_files = ['pyproject.toml', 'setup.py', 'requirements.txt', '.pre-commit-config.yaml']
for item in key_dirs + key_files:
    print(f'✓ {item}' if os.path.exists(item) else f'✗ {item} MISSING')
"

# Detailed project analysis
python -c "
import os
src_path = 'src/accessiweather'
if os.path.exists(src_path):
    files = [f for f in os.listdir(src_path) if f.endswith('.py')]
    print(f'Python modules: {len(files)}')
    key_modules = ['main.py', 'config_utils.py', 'cli.py', 'constants.py']
    for mod in key_modules:
        print(f'  {\"✓\" if mod in files else \"✗\"} {mod}')

test_files = len([f for f in os.listdir('tests') if f.startswith('test_')])
print(f'Test files: {test_files}')

workflows = len([f for f in os.listdir('.github/workflows') if f.endswith('.yml')])
print(f'CI workflows: {workflows}')
"
```

### After Making Changes, ALWAYS:
1. **Test core functionality**:
   ```bash
   # Test basic imports and utilities (works without wxPython)
   python -c "
   import sys; sys.path.insert(0, 'src')
   from accessiweather.utils.temperature_utils import fahrenheit_to_celsius
   from accessiweather import config_utils, constants
   print('Core components working')
   print(f'Temperature test: 32°F = {fahrenheit_to_celsius(32.0)}°C')
   "
   ```

2. **Validate version consistency**:
   ```bash
   echo "=== Version check ==="
   grep -n "version.*=" setup.py pyproject.toml
   ```

3. **Run relevant tests** (if wxPython available):
   ```bash
   python -m pytest tests/test_temperature_utils.py -v
   python -m pytest tests/test_config_utils.py -v
   ```

4. **Check code quality** (if tools available):
   ```bash
   pre-commit run --all-files
   # OR manually:
   black --check src/
   isort --check-only src/
   flake8 src/
   ```

### Build Readiness Check
```bash
# Verify PyInstaller availability and timing
time python -c "
import PyInstaller.__main__
print(f'PyInstaller version: {PyInstaller.__version__}')
print('PyInstaller ready for builds')
"

# Check build scripts exist
ls -la installer/build_installer.*

# Quick PyInstaller test (takes ~8 seconds)
mkdir -p /tmp/build_test
echo "print('Build test OK')" > /tmp/build_test/test.py
time python -m PyInstaller --onefile /tmp/build_test/test.py --distpath /tmp/build_test/dist --workpath /tmp/build_test/build --specpath /tmp/build_test
rm -rf /tmp/build_test
```

## Known Issues and Limitations

### Critical Constraints
- **wxPython dependency**: Most application functionality requires wxPython, which often fails to install due to network/firewall issues
- **Network dependency**: All pip installations require stable internet connection with generous timeouts  
- **Windows-focused build**: Primary build targets Windows executables via PyInstaller
- **GUI test limitations**: GUI tests may be flaky in headless CI environments
- **CLI requires GUI**: Even the CLI entry point requires wxPython due to module dependencies

### Working Workarounds
- **Core utilities testing**: Non-GUI components can be tested without wxPython
- **Build validation**: PyInstaller functionality can be verified without full builds
- **Incremental development**: Focus on core logic in `src/accessiweather/utils/` before GUI integration
- **Version management**: Versions are in both `setup.py` (0.9.3) and `pyproject.toml` (0.9.3.1) - keep synchronized

### Timeout Requirements
- **pip operations**: Minimum 600 seconds, recommend 1800 seconds
- **PyInstaller builds**: Minimum 1800 seconds, recommend 3600 seconds
- **Test execution**: Minimum 300 seconds for full test suite
- **CI pipeline**: Allow 45+ minutes for complete pipeline

## Repository Navigation

### Key Files and Directories
- **Main application**: `src/accessiweather/main.py`
- **Core utilities**: `src/accessiweather/utils/`
- **API clients**: `src/accessiweather/` (various *_client.py files)
- **GUI components**: `src/accessiweather/gui/`
- **Tests**: `tests/` (comprehensive test suite)
- **Build scripts**: `installer/` (PowerShell and bash build scripts)
- **CI/CD**: `.github/workflows/` (comprehensive GitHub Actions)
- **Configuration**: `pyproject.toml`, `setup.py`, various dot-files

### Frequently Modified Areas
- **Weather API integration**: `src/accessiweather/openmeteo_client.py`, `src/accessiweather/api_client.py`
- **Settings and configuration**: `src/accessiweather/config_utils.py`, `src/accessiweather/gui/settings_dialog.py`
- **Temperature handling**: `src/accessiweather/utils/temperature_utils.py`
- **Test infrastructure**: `tests/conftest.py`, `tests/run_integration_tests.py`

### CI/CD Pipeline Files
- **Main CI**: `.github/workflows/ci.yml` (comprehensive quality gates)
- **Build pipeline**: `.github/workflows/build.yml` (PyInstaller Windows builds)
- **Release pipeline**: `.github/workflows/release.yml` (automated releases)

## Common Development Scenarios

### Working on Core Logic (Recommended Start)
1. **Focus on utilities first**: Work in `src/accessiweather/utils/` - these don't require wxPython
2. **Test immediately**: `python -c "import sys; sys.path.insert(0, 'src'); from accessiweather.utils.temperature_utils import *"`
3. **Iterate quickly**: Core utilities can be tested without full environment setup

### Working on API Integration
1. **Test API clients**: Work in `src/accessiweather/openmeteo_client.py`, `src/accessiweather/api_client.py`
2. **Use mock data**: Check `tests/mock_data.py` for examples
3. **Network independence**: Most API logic can be developed offline with mocks

### Working on Configuration
1. **Config utilities**: `src/accessiweather/config_utils.py` works without GUI dependencies
2. **Test config loading**: Validate with repository health checks
3. **Version management**: Keep `setup.py` and `pyproject.toml` versions synchronized

### Preparing for GUI Work
1. **Install wxPython first**: `pip install --timeout=1800 wxPython` (expect 10-30 minutes)
2. **Test GUI imports**: `python -c "import wx; print('wxPython working')"`
3. **Run full tests**: Only after wxPython is successfully installed

## Project Context

AccessiWeather provides weather information with a focus on accessibility for screen reader users. It integrates with National Weather Service (US) and Open-Meteo (international) APIs, supports multiple weather data sources, and creates Windows desktop applications via PyInstaller.

**Architecture Summary**:
- **Core**: Python 3.7+ with 20 modules, 40+ tests, comprehensive CI/CD
- **GUI**: wxPython desktop application with accessibility features  
- **Build**: PyInstaller for Windows executables, PowerShell/bash scripts
- **APIs**: NWS (US weather + alerts) and Open-Meteo (international weather)
- **Distribution**: GitHub Actions CI/CD with 5 workflows, Windows installer generation

The development workflow emphasizes comprehensive testing, code quality checks, and automated CI/CD with generous timeout allowances for build processes that can take 30+ minutes to complete.