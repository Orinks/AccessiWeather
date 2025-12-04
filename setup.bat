@echo off
setlocal enabledelayedexpansion

echo ========================================
echo AccessiWeather Worktree Setup
echo ========================================
echo.

set "VENV_DIR=.venv"

if exist "%VENV_DIR%\Scripts\python.exe" (
    echo Virtual environment already exists at %VENV_DIR%
    echo Skipping venv creation...
) else (
    echo Creating virtual environment at %VENV_DIR%...
    python -m venv %VENV_DIR%
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment
        exit /b 1
    )
)

echo.
echo Activating virtual environment...
call "%VENV_DIR%\Scripts\activate.bat"

echo.
echo Upgrading pip...
python -m pip install --upgrade pip
if errorlevel 1 (
    echo ERROR: Failed to upgrade pip
    exit /b 1
)

echo.
echo Installing project with dev dependencies...
pip install -e ".[dev,audio]"
if errorlevel 1 (
    echo ERROR: Failed to install project dependencies
    exit /b 1
)

echo.
echo Installing Briefcase for build/packaging...
pip install briefcase
if errorlevel 1 (
    echo ERROR: Failed to install Briefcase
    exit /b 1
)

echo.
echo ========================================
echo Setup complete!
echo ========================================
echo.
echo To activate the environment, run:
echo     %VENV_DIR%\Scripts\activate.bat
echo.
echo Common commands:
echo     python installer/make.py dev     - Run app in dev mode
echo     python installer/make.py test    - Run tests
echo     pytest                           - Run tests directly
echo     ruff check .                     - Lint code
echo     ruff format .                    - Format code
echo.

endlocal
