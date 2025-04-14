@echo off
echo ===== Building AccessiWeather Installer =====

REM Set environment variables
set APP_NAME=AccessiWeather
set APP_VERSION=0.9.0
set PYTHON_EXE=python
set PYINSTALLER_OPTS=--clean --noconfirm --onedir --windowed --name %APP_NAME%

REM Create build directories if they don't exist
if not exist "dist" mkdir dist
if not exist "build" mkdir build

echo.
echo ===== Step 1: Installing required packages =====
%PYTHON_EXE% -m pip install -U pyinstaller

echo.
echo ===== Step 2: Building executable with PyInstaller =====
%PYTHON_EXE% -m PyInstaller %PYINSTALLER_OPTS% ^
    --hidden-import=plyer.platforms.win.notification ^
    --hidden-import=dateutil.parser ^
    src/accessiweather/main.py

echo.
echo ===== Step 3: Creating portable ZIP archive =====
powershell -Command "Compress-Archive -Path dist\%APP_NAME%\* -DestinationPath dist\%APP_NAME%_Portable_v%APP_VERSION%.zip -Force"

echo.
echo ===== Step 4: Building installer with Inno Setup =====
echo Checking for Inno Setup...

REM Check if Inno Setup is installed
where /q iscc
if %ERRORLEVEL% NEQ 0 (
    echo Inno Setup Compiler (iscc) not found in PATH.
    echo Please install Inno Setup from https://jrsoftware.org/isdl.php
    echo and make sure it's added to your PATH.
    exit /b 1
)

echo Building installer...
iscc installer\AccessiWeather.iss

echo.
echo ===== Build Complete =====
echo Installer: dist\%APP_NAME%_Setup_v%APP_VERSION%.exe
echo Portable: dist\%APP_NAME%_Portable_v%APP_VERSION%.zip
echo.
