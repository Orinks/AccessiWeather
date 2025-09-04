# AccessiWeather Development Startup Script (PowerShell)
# This script starts the AccessiWeather application in development mode using Briefcase

param(
    [switch]$Verbose
)

$ErrorActionPreference = "Stop"

$PROJECT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Definition
$VENV_PATH = Join-Path $PROJECT_DIR ".venv"

Write-Host "Starting AccessiWeather development server..." -ForegroundColor Green
Write-Host "Project directory: $PROJECT_DIR"

# Change to project directory
Set-Location $PROJECT_DIR

# Check if virtual environment exists
if (-not (Test-Path $VENV_PATH)) {
    Write-Host "Error: Virtual environment not found at $VENV_PATH" -ForegroundColor Red
    Write-Host "Please create a virtual environment first by running:" -ForegroundColor Yellow
    Write-Host "  uv venv" -ForegroundColor Yellow
    Write-Host "  uv pip install -e ." -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Cyan
$ActivateScript = Join-Path $VENV_PATH "Scripts\Activate.ps1"

if (Test-Path $ActivateScript) {
    & $ActivateScript
} else {
    Write-Host "Error: Could not find activation script at $ActivateScript" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Check if briefcase is installed
try {
    $null = Get-Command briefcase -ErrorAction Stop
} catch {
    Write-Host "Installing briefcase..." -ForegroundColor Yellow
    try {
        & uv pip install briefcase
    } catch {
        Write-Host "Error: Failed to install briefcase. Trying with pip..." -ForegroundColor Yellow
        & pip install briefcase
    }
}

# Check if the app is configured for briefcase
if (-not (Test-Path "pyproject.toml")) {
    Write-Host "Error: pyproject.toml not found. This doesn't appear to be a Briefcase project." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "Starting AccessiWeather in development mode..." -ForegroundColor Green
Write-Host "Press Ctrl+C to stop the application" -ForegroundColor Yellow
Write-Host ""

# Start the application in development mode
try {
    & briefcase dev
} catch {
    Write-Host "Error: Failed to start application with briefcase dev" -ForegroundColor Red
    Write-Host "Error details: $_" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
