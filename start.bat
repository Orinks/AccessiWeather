@echo off
REM AccessiWeather Development Startup Script (Windows)
REM This script starts the AccessiWeather application in development mode using Briefcase

setlocal enabledelayedexpansion

set PROJECT_DIR=%~dp0
set VENV_PATH=%PROJECT_DIR%.venv

echo Starting AccessiWeather development server...
echo Project directory: %PROJECT_DIR%

REM Change to project directory
cd /d "%PROJECT_DIR%"

REM Check if virtual environment exists
if not exist "%VENV_PATH%" (
    echo Error: Virtual environment not found at %VENV_PATH%
    echo Please create a virtual environment first by running:
    echo   uv venv
    echo   uv pip install -e .
    pause
    exit /b 1
)

REM Activate virtual environment
echo Activating virtual environment...
call "%VENV_PATH%\Scripts\activate.bat"
if errorlevel 1 (
    echo Error: Failed to activate virtual environment
    pause
    exit /b 1
)

REM Check if briefcase is installed
where briefcase >nul 2>&1
if errorlevel 1 (
    echo Installing briefcase...
    uv pip install briefcase
    if errorlevel 1 (
        echo Error: Failed to install briefcase
        pause
        exit /b 1
    )
)

REM Check if the app is configured for briefcase
if not exist "pyproject.toml" (
    echo Error: pyproject.toml not found. This doesn't appear to be a Briefcase project.
    pause
    exit /b 1
)

echo Starting AccessiWeather in development mode...
echo Press Ctrl+C to stop the application
echo.

REM Start the application in development mode
briefcase dev
