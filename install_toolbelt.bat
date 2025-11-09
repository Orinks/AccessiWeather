@echo off
REM Install toolbelt utilities for AccessiWeather development
REM This script must be run as Administrator

echo ============================================================
echo Installing Development Toolbelt Utilities
echo ============================================================
echo.
echo This script will install the following tools via Chocolatey:
echo   - fd         : Fast file finder
echo   - ripgrep    : Fast code search
echo   - jq         : JSON processor
echo   - bat        : Cat with syntax highlighting
echo   - eza        : Modern ls
echo   - zoxide     : Smart cd
echo   - git-delta  : Better git diff
echo.
echo NOTE: httpie is already installed in the Python virtualenv
echo.

REM Check for admin rights
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo ERROR: This script requires Administrator privileges
    echo Please right-click and select "Run as Administrator"
    pause
    exit /b 1
)

echo Installing packages...
echo.

choco install fd ripgrep jq bat eza zoxide git-delta -y

echo.
echo ============================================================
echo Installation Complete
echo ============================================================
echo.
echo You may need to restart your terminal for PATH changes to take effect.
echo.
echo To test the installation, run:
echo   python test_toolbelt.py
echo.
pause
