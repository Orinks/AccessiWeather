# AccessiWeather Installer Build Script
# This PowerShell script builds the AccessiWeather application and creates an installer

# Determine script location and project root
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = (Get-Item $ScriptDir).Parent.FullName

# Change to project root directory if we're in the installer directory
$CurrentDir = (Get-Location).Path
if ($CurrentDir -eq $ScriptDir) {
    Write-Host "Running from installer directory. Changing to project root..." -ForegroundColor Yellow
    Set-Location $ProjectRoot
    Write-Host "Working directory set to: $ProjectRoot" -ForegroundColor Green
}

# Function to extract version from setup.py
function Get-AppVersion {
    $setupPath = Join-Path $ProjectRoot "setup.py"
    if (Test-Path $setupPath) {
        $versionLine = Get-Content $setupPath | Where-Object { $_ -match 'version\s*=\s*"([0-9\.]+)"' }
        if ($versionLine -match 'version\s*=\s*"([0-9\.]+)"') {
            return $matches[1]
        }
    }
    Write-Host "Warning: Could not extract version from setup.py. Using default version." -ForegroundColor Yellow
    return "0.0.0"
}

# Set environment variables
$AppName = "AccessiWeather"
$AppVersion = Get-AppVersion
$PyInstallerOpts = "--clean", "--noconfirm", "--onedir", "--windowed", "--name", $AppName

Write-Host "Building $AppName version $AppVersion" -ForegroundColor Cyan

# Function to check for running processes that might interfere with the build
function Check-RunningProcesses {
    Write-Host "`n===== Checking for processes that might interfere with the build =====" -ForegroundColor Yellow

    # Check if the application is running
    $appProcesses = Get-Process -Name $AppName -ErrorAction SilentlyContinue

    # Check for Python processes that might be related to our app
    $pythonProcesses = Get-Process -Name "python", "pythonw" -ErrorAction SilentlyContinue | Where-Object {
        $_.MainWindowTitle -like "*$AppName*" -or
        $_.CommandLine -like "*$AppName*" -or
        $_.CommandLine -like "*accessiweather*"
    }

    # Check for other processes that might lock files in the dist directory
    $distPath = Resolve-Path "dist" -ErrorAction SilentlyContinue
    $buildPath = Resolve-Path "build" -ErrorAction SilentlyContinue
    $processesLockingFiles = @()

    # Basic check using PowerShell
    if ($distPath) {
        # Get processes that have handles to files in the dist directory
        $distProcesses = Get-Process | Where-Object {
            $_.Modules | Where-Object {
                $_.FileName -like "$distPath*"
            }
        } | Select-Object -Property Id, ProcessName, Path

        $processesLockingFiles += $distProcesses
    }

    if ($buildPath) {
        # Get processes that have handles to files in the build directory
        $buildProcesses = Get-Process | Where-Object {
            $_.Modules | Where-Object {
                $_.FileName -like "$buildPath*"
            }
        } | Select-Object -Property Id, ProcessName, Path

        $processesLockingFiles += $buildProcesses
    }

    # Check for any processes that might have the executable open
    $exePath = "dist\$AppName\$AppName.exe"
    if (Test-Path $exePath) {
        try {
            # Try to rename the file temporarily - if it fails, it's likely in use
            $tempPath = "$exePath.temp"
            Rename-Item -Path $exePath -NewName $tempPath -ErrorAction Stop
            Rename-Item -Path $tempPath -NewName $exePath -ErrorAction Stop
            Write-Host "Executable file is not locked." -ForegroundColor Green
        } catch {
            Write-Host "Executable file appears to be locked by a process." -ForegroundColor Yellow
        }
    }

    # Combine all detected processes
    $allProcesses = @($appProcesses) + @($pythonProcesses) + $processesLockingFiles |
                    Select-Object -Property Id, ProcessName, Path -Unique

    if ($allProcesses.Count -gt 0) {
        Write-Host "The following processes might interfere with the build process:" -ForegroundColor Red
        $allProcesses | ForEach-Object {
            Write-Host "  - $($_.ProcessName) (PID: $($_.Id))" -ForegroundColor Red
        }

        $confirmation = Read-Host "Do you want to attempt to close these processes? (Y/N)"
        if ($confirmation -eq 'Y' -or $confirmation -eq 'y') {
            $allProcesses | ForEach-Object {
                try {
                    Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
                    Write-Host "Closed process: $($_.ProcessName) (PID: $($_.Id))" -ForegroundColor Green
                } catch {
                    Write-Host "Failed to close process: $($_.ProcessName) (PID: $($_.Id))" -ForegroundColor Red
                }
            }

            # Give processes time to fully close
            Start-Sleep -Seconds 2

            # Check if any processes are still running
            $remainingProcesses = $allProcesses | Where-Object {
                Get-Process -Id $_.Id -ErrorAction SilentlyContinue
            }

            if ($remainingProcesses.Count -gt 0) {
                Write-Host "Some processes could not be closed:" -ForegroundColor Red
                $remainingProcesses | ForEach-Object {
                    Write-Host "  - $($_.ProcessName) (PID: $($_.Id))" -ForegroundColor Red
                }

                $continue = Read-Host "Continue anyway? (Y/N)"
                if ($continue -ne 'Y' -and $continue -ne 'y') {
                    exit 1
                }
            }
        } else {
            Write-Host "Please close these processes manually before continuing." -ForegroundColor Yellow
            $continue = Read-Host "Continue anyway? (Y/N)"
            if ($continue -ne 'Y' -and $continue -ne 'y') {
                exit 1
            }
        }
    } else {
        Write-Host "No interfering processes detected." -ForegroundColor Green
    }
}

# Function to clean build directories
function Clean-BuildDirectories {
    Write-Host "`n===== Cleaning build directories =====" -ForegroundColor Yellow

    # Ask user if they want to clean the directories
    $cleanDirs = Read-Host "Do you want to clean the build and dist directories before building? (Y/N)"

    if ($cleanDirs -eq 'Y' -or $cleanDirs -eq 'y') {
        # Clean dist directory
        if (Test-Path "dist") {
            Write-Host "Cleaning dist directory..." -ForegroundColor Yellow
            try {
                Remove-Item -Path "dist" -Recurse -Force
                Write-Host "dist directory cleaned successfully." -ForegroundColor Green
            } catch {
                Write-Host "Error cleaning dist directory: $_" -ForegroundColor Red
                Write-Host "Some files may be locked by other processes." -ForegroundColor Red
            }
        }

        # Clean build directory
        if (Test-Path "build") {
            Write-Host "Cleaning build directory..." -ForegroundColor Yellow
            try {
                Remove-Item -Path "build" -Recurse -Force
                Write-Host "build directory cleaned successfully." -ForegroundColor Green
            } catch {
                Write-Host "Error cleaning build directory: $_" -ForegroundColor Red
                Write-Host "Some files may be locked by other processes." -ForegroundColor Red
            }
        }

        # Clean spec file
        if (Test-Path "$AppName.spec") {
            Write-Host "Removing spec file..." -ForegroundColor Yellow
            try {
                Remove-Item -Path "$AppName.spec" -Force
                Write-Host "Spec file removed successfully." -ForegroundColor Green
            } catch {
                Write-Host "Error removing spec file: $_" -ForegroundColor Red
            }
        }
    }
}

# Create build directories if they don't exist
if (-not (Test-Path "dist")) {
    New-Item -Path "dist" -ItemType Directory | Out-Null
}
if (-not (Test-Path "build")) {
    New-Item -Path "build" -ItemType Directory | Out-Null
}

# Check for running processes
Check-RunningProcesses

# Clean build directories if requested
Clean-BuildDirectories

# Step 1: Install required packages
Write-Host "`n===== Step 1: Installing required packages =====" -ForegroundColor Cyan
python -m pip install -U pyinstaller

# Step 2: Build executable with PyInstaller
Write-Host "`n===== Step 2: Building executable with PyInstaller =====" -ForegroundColor Cyan
$PyInstallerArgs = $PyInstallerOpts + @(
    "--hidden-import=plyer.platforms.win.notification",
    "--hidden-import=dateutil.parser",
    "src/accessiweather/main.py"
)
python -m PyInstaller $PyInstallerArgs

# Step 3: Create portable ZIP archive
Write-Host "`n===== Step 3: Creating portable ZIP archive =====" -ForegroundColor Cyan
Compress-Archive -Path "dist\$AppName\*" -DestinationPath "dist\${AppName}_Portable_v${AppVersion}.zip" -Force

# Step 4: Build installer with Inno Setup
Write-Host "`n===== Step 4: Building installer with Inno Setup =====" -ForegroundColor Cyan
Write-Host "Checking for Inno Setup..." -ForegroundColor Yellow

# Check if Inno Setup is installed
try {
    $isccPath = (Get-Command "iscc" -ErrorAction Stop).Source
    Write-Host "Found Inno Setup at: $isccPath" -ForegroundColor Green
} catch {
    # Try common installation paths
    $commonPaths = @(
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe"
    )

    $found = $false
    foreach ($path in $commonPaths) {
        if (Test-Path $path) {
            $isccPath = $path
            $found = $true
            Write-Host "Found Inno Setup at: $isccPath" -ForegroundColor Green

            # Add to PATH for this session
            $env:Path += ";$(Split-Path $isccPath)"
            Write-Host "Added Inno Setup to PATH for this session" -ForegroundColor Yellow
            break
        }
    }

    if (-not $found) {
        Write-Host "Inno Setup Compiler (iscc) not found in PATH or common locations." -ForegroundColor Red
        Write-Host "Please install Inno Setup from https://jrsoftware.org/isdl.php" -ForegroundColor Red
        Write-Host "and make sure it's added to your PATH." -ForegroundColor Red
        Write-Host "
To add Inno Setup to PATH permanently:" -ForegroundColor Cyan
        Write-Host "1. Press Win + X and select 'System'" -ForegroundColor Cyan
        Write-Host "2. Click on 'Advanced system settings'" -ForegroundColor Cyan
        Write-Host "3. Click the 'Environment Variables' button" -ForegroundColor Cyan
        Write-Host "4. In the 'System variables' section, find and select the 'Path' variable" -ForegroundColor Cyan
        Write-Host "5. Click 'Edit'" -ForegroundColor Cyan
        Write-Host "6. Click 'New' and add 'C:\Program Files (x86)\Inno Setup 6'" -ForegroundColor Cyan
        Write-Host "7. Click 'OK' on all dialogs to save the changes" -ForegroundColor Cyan
        exit 1
    }
}

Write-Host "Building installer..." -ForegroundColor Yellow
$issPath = Join-Path $ScriptDir "AccessiWeather.iss"
Write-Host "Using Inno Setup script: $issPath" -ForegroundColor Yellow

# Set environment variables for Inno Setup to use absolute paths
$env:ACCESSIWEATHER_ROOT_DIR = $ProjectRoot
$env:ACCESSIWEATHER_DIST_DIR = Join-Path $ProjectRoot "dist"
$env:ACCESSIWEATHER_VERSION = $AppVersion
Write-Host "Setting environment variables for Inno Setup:" -ForegroundColor Yellow
Write-Host "  ACCESSIWEATHER_ROOT_DIR = $($env:ACCESSIWEATHER_ROOT_DIR)" -ForegroundColor Yellow
Write-Host "  ACCESSIWEATHER_DIST_DIR = $($env:ACCESSIWEATHER_DIST_DIR)" -ForegroundColor Yellow
Write-Host "  ACCESSIWEATHER_VERSION = $($env:ACCESSIWEATHER_VERSION)" -ForegroundColor Yellow

if ($found) {
    & $isccPath $issPath
} else {
    & iscc $issPath
}

# Clean up environment variables
$env:ACCESSIWEATHER_ROOT_DIR = $null
$env:ACCESSIWEATHER_DIST_DIR = $null
$env:ACCESSIWEATHER_VERSION = $null

# Final message
Write-Host "`n===== Build Complete =====" -ForegroundColor Green
Write-Host "Installer: dist\${AppName}_Setup_v${AppVersion}.exe" -ForegroundColor Cyan
Write-Host "Portable: dist\${AppName}_Portable_v${AppVersion}.zip" -ForegroundColor Cyan

# Check for any processes that might have been started during the build
Write-Host "`n===== Checking for new processes =====" -ForegroundColor Yellow
$newProcesses = Get-Process | Where-Object {
    ($_.ProcessName -eq $AppName) -or
    ($_.ProcessName -like "python*" -and $_.MainWindowTitle -like "*$AppName*") -or
    ($_.ProcessName -like "python*" -and $_.CommandLine -like "*$AppName*") -or
    ($_.ProcessName -like "python*" -and $_.CommandLine -like "*accessiweather*")
}

if ($newProcesses.Count -gt 0) {
    Write-Host "The following processes were started during the build:" -ForegroundColor Yellow
    $newProcesses | ForEach-Object {
        Write-Host "  - $($_.ProcessName) (PID: $($_.Id))" -ForegroundColor Yellow
    }

    $closeProcesses = Read-Host "Do you want to close these processes? (Y/N)"
    if ($closeProcesses -eq 'Y' -or $closeProcesses -eq 'y') {
        $newProcesses | ForEach-Object {
            try {
                Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
                Write-Host "Closed process: $($_.ProcessName) (PID: $($_.Id))" -ForegroundColor Green
            } catch {
                Write-Host "Failed to close process: $($_.ProcessName) (PID: $($_.Id))" -ForegroundColor Red
            }
        }
    }
} else {
    Write-Host "No new processes were detected." -ForegroundColor Green
}

# Verify output files
Write-Host "`n===== Verifying output files =====" -ForegroundColor Yellow
$installerPath = "dist\${AppName}_Setup_v${AppVersion}.exe"
$portablePath = "dist\${AppName}_Portable_v${AppVersion}.zip"
$executablePath = "dist\$AppName\$AppName.exe"

$allFilesExist = $true

if (Test-Path $executablePath) {
    Write-Host "✓ Executable created successfully: $executablePath" -ForegroundColor Green
} else {
    Write-Host "✗ Executable was not created: $executablePath" -ForegroundColor Red
    $allFilesExist = $false
}

if (Test-Path $installerPath) {
    $installerSize = (Get-Item $installerPath).Length / 1MB
    Write-Host "✓ Installer created successfully: $installerPath (Size: $($installerSize.ToString("0.00")) MB)" -ForegroundColor Green
} else {
    Write-Host "✗ Installer was not created: $installerPath" -ForegroundColor Red
    $allFilesExist = $false
}

if (Test-Path $portablePath) {
    $portableSize = (Get-Item $portablePath).Length / 1MB
    Write-Host "✓ Portable ZIP created successfully: $portablePath (Size: $($portableSize.ToString("0.00")) MB)" -ForegroundColor Green
} else {
    Write-Host "✗ Portable ZIP was not created: $portablePath" -ForegroundColor Red
    $allFilesExist = $false
}

if ($allFilesExist) {
    Write-Host "`nBuild process completed successfully!" -ForegroundColor Green
} else {
    Write-Host "`nBuild process completed with errors. Some output files are missing." -ForegroundColor Red
}
