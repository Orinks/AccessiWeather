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

# Function to extract version from pyproject.toml
function Get-AppVersion {
    $pyprojectPath = Join-Path $ProjectRoot "pyproject.toml"
    if (Test-Path $pyprojectPath) {
        $versionLine = Get-Content $pyprojectPath | Where-Object { $_ -match 'version\s*=\s*"([0-9\.]+)"' }
        if ($versionLine -match 'version\s*=\s*"([0-9\.]+)"') {
            return $matches[1]
        }
    }
    Write-Host "Warning: Could not extract version from pyproject.toml. Using default version." -ForegroundColor Yellow
    return "0.0.0"
}

# Set environment variables
$AppName = "AccessiWeather"
$AppVersion = Get-AppVersion
$PyInstallerOpts = "--clean", "--noconfirm", "--onedir", "--windowed", "--name", $AppName

Write-Host "Building $AppName version $AppVersion" -ForegroundColor Cyan

# Function to test for running processes that might interfere with the build
function Test-RunningProcesses {
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
        }
        catch {
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

        # Automatically close interfering processes without asking
        Write-Host "Automatically closing interfering processes..." -ForegroundColor Yellow
        $allProcesses | ForEach-Object {
            try {
                Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
                Write-Host "Closed process: $($_.ProcessName) (PID: $($_.Id))" -ForegroundColor Green
            }
            catch {
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
            Write-Host "Continuing anyway..." -ForegroundColor Yellow
        }
    }
    else {
        Write-Host "No interfering processes detected." -ForegroundColor Green
    }
}

# Function to remove build directories
function Remove-BuildDirectories {
    Write-Host "`n===== Cleaning build directories =====" -ForegroundColor Yellow

    # Automatically clean the directories without asking
    Write-Host "Automatically cleaning build and dist directories..." -ForegroundColor Yellow

    # Clean dist directory
    if (Test-Path "dist") {
        Write-Host "Cleaning dist directory..." -ForegroundColor Yellow
        try {
            Remove-Item -Path "dist" -Recurse -Force
            Write-Host "dist directory cleaned successfully." -ForegroundColor Green
        }
        catch {
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
        }
        catch {
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
        }
        catch {
            Write-Host "Error removing spec file: $_" -ForegroundColor Red
        }
    }
}

# Function to compare version strings
function Compare-Version {
    param (
        [string]$Version1,
        [string]$Version2
    )

    $v1 = [version]$Version1
    $v2 = [version]$Version2

    if ($v1 -gt $v2) { return 1 }
    if ($v1 -lt $v2) { return -1 }
    return 0
}

# Function to test if Python is installed with the minimum required version
function Test-PythonInstalled {
    param (
        [string]$MinVersion = "3.6.0"
    )

    try {
        $pythonVersion = python --version 2>&1
        if ($pythonVersion -match 'Python (\d+\.\d+\.\d+)') {
            $currentVersion = $matches[1]
            $versionComparison = Compare-Version -Version1 $currentVersion -Version2 $MinVersion

            if ($versionComparison -ge 0) {
                Write-Host "Python $currentVersion is installed (minimum required: $MinVersion)" -ForegroundColor Green
                return $true
            }
            else {
                Write-Host "Python $currentVersion is installed but version $MinVersion or higher is required" -ForegroundColor Yellow
                return $false
            }
        }
    }
    catch {
        Write-Host "Python is not installed or not in PATH" -ForegroundColor Red
        return $false
    }

    return $false
}

# Function to get the list of required dependencies
function Get-RequiredDependencies {
    # Define the list of required dependencies based on setup.py
    $dependencies = @(
        "wxPython",
        "requests",
        "plyer",
        "geopy",
        "python-dateutil",
        "beautifulsoup4",
        "httpx",
        "attrs",
        "PyInstaller"
    )

    return $dependencies
}

# Function to test if a specific package is installed
function Test-DependencyInstalled {
    param (
        [string]$PackageName
    )

    try {
        $pipList = pip list 2>&1
        $packagePattern = "^$PackageName\s+(\d+\.\d+\.\d+)"

        foreach ($line in $pipList) {
            if ($line -match $packagePattern) {
                Write-Host "$PackageName $($matches[1]) is installed" -ForegroundColor Green
                return $true
            }
        }

        Write-Host "$PackageName is not installed" -ForegroundColor Yellow
        return $false
    }
    catch {
        $errorMessage = $_.Exception.Message
        Write-Host "Error checking if $PackageName is installed - $errorMessage" -ForegroundColor Red
        return $false
    }
}

# Function to install a specific package
function Install-Dependency {
    param (
        [string]$PackageName,
        [switch]$Upgrade
    )

    $upgradeFlag = if ($Upgrade) { "--upgrade" } else { "" }

    try {
        Write-Host "Installing $PackageName..." -ForegroundColor Cyan

        # Special handling for wxPython which might need specific installation parameters
        if ($PackageName -eq "wxPython") {
            $result = pip install $upgradeFlag --no-cache-dir $PackageName 2>&1
        }
        else {
            $result = pip install $upgradeFlag $PackageName 2>&1
        }

        if (Test-DependencyInstalled -PackageName $PackageName) {
            Write-Host "$PackageName installed successfully" -ForegroundColor Green
            return $true
        }
        else {
            Write-Host "Failed to install $PackageName" -ForegroundColor Red
            Write-Host $result -ForegroundColor Red
            return $false
        }
    }
    catch {
        $errorMessage = $_.Exception.Message
        Write-Host "Error installing $PackageName - $errorMessage" -ForegroundColor Red
        return $false
    }
}

# Function to test and install all required dependencies
function Test-InstallDependencies {
    param (
        [switch]$Force
    )

    $allDependenciesInstalled = $true
    $dependencies = Get-RequiredDependencies

    foreach ($dependency in $dependencies) {
        if (-not (Test-DependencyInstalled -PackageName $dependency) -or $Force) {
            $installSuccess = Install-Dependency -PackageName $dependency -Upgrade:$Force
            if (-not $installSuccess) {
                $allDependenciesInstalled = $false
            }
        }
    }

    return $allDependenciesInstalled
}

# Create build directories if they don't exist
if (-not (Test-Path "dist")) {
    New-Item -Path "dist" -ItemType Directory | Out-Null
}
if (-not (Test-Path "build")) {
    New-Item -Path "build" -ItemType Directory | Out-Null
}

# Check for running processes
Test-RunningProcesses

# Clean build directories if requested
Remove-BuildDirectories

# Step 1: Check and install dependencies
Write-Host "`n===== Step 1: Checking and installing dependencies =====" -ForegroundColor Cyan

# Check if Python is installed
if (-not (Test-PythonInstalled)) {
    Write-Host "Please install Python 3.6 or higher and add it to your PATH" -ForegroundColor Red
    exit 1
}

# Check and install dependencies
Write-Host "Checking and installing dependencies..." -ForegroundColor Cyan
$dependenciesInstalled = Test-InstallDependencies

if (-not $dependenciesInstalled) {
    Write-Host "Failed to install all required dependencies. Please check the error messages above." -ForegroundColor Red

    # In non-interactive environments (like CI), automatically retry with -Force
    if ($env:CI -eq "true" -or $env:GITHUB_ACTIONS -eq "true") {
        Write-Host "Running in CI environment, automatically retrying with -Force option..." -ForegroundColor Yellow
        $dependenciesInstalled = Test-InstallDependencies -Force
        if (-not $dependenciesInstalled) {
            Write-Host "Failed to install all required dependencies even with the -Force option." -ForegroundColor Red
            exit 1
        }
    }
    else {
        $retry = Read-Host "Do you want to retry with the -Force option to reinstall all dependencies? (y/n)"
        if ($retry -eq "y") {
            $dependenciesInstalled = Test-InstallDependencies -Force
            if (-not $dependenciesInstalled) {
                Write-Host "Failed to install all required dependencies even with the -Force option. Please install them manually." -ForegroundColor Red
                exit 1
            }
        }
        else {
            exit 1
        }
    }
}

Write-Host "All dependencies are installed successfully." -ForegroundColor Green

# Step 2: Build executable with PyInstaller
Write-Host "`n===== Step 2: Building executable with PyInstaller =====" -ForegroundColor Cyan
Write-Host "Using spec file to exclude unnecessary packages (Django, IPython, etc.)" -ForegroundColor Yellow

# Check if spec file exists
$SpecFile = Join-Path $ProjectRoot "AccessiWeather.spec"
if (Test-Path $SpecFile) {
    Write-Host "Using spec file: $SpecFile" -ForegroundColor Green
    $pyinstallerProcess = Start-Process -FilePath "python" -ArgumentList "-m", "PyInstaller", "--clean", "--noconfirm", $SpecFile -Wait -PassThru -NoNewWindow
    if ($pyinstallerProcess.ExitCode -ne 0) {
        Write-Host "PyInstaller failed with exit code: $($pyinstallerProcess.ExitCode)" -ForegroundColor Red
        exit 1
    }
}
else {
    Write-Host "Warning: Spec file not found, falling back to command line arguments" -ForegroundColor Yellow
    $PyInstallerArgs = @("-m", "PyInstaller") + $PyInstallerOpts + @(
        "--hidden-import=plyer.platforms.win.notification",
        "--hidden-import=dateutil.parser",
        "--hidden-import=httpx",
        "--hidden-import=attrs",
        "--exclude-module=IPython",
        "--exclude-module=jedi",
        "--exclude-module=parso",
        "--exclude-module=black",
        "--exclude-module=mypy",
        "--exclude-module=django",
        "--exclude-module=Django",
        "--exclude-module=rapidfuzz",
        "src/accessiweather/main.py"
    )
    # Use Invoke-Expression to avoid environment variable conflicts
    $pyinstallerCommand = "python " + ($PyInstallerArgs -join " ")
    Write-Host "Running: $pyinstallerCommand" -ForegroundColor Yellow
    $pyinstallerResult = Invoke-Expression $pyinstallerCommand
    $pyinstallerExitCode = $LASTEXITCODE
    if ($pyinstallerExitCode -ne 0) {
        Write-Host "PyInstaller failed with exit code: $pyinstallerExitCode" -ForegroundColor Red
        exit 1
    }
}

Write-Host "PyInstaller completed successfully." -ForegroundColor Green
Start-Sleep -Seconds 2

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
}
catch {
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
        Write-Host "`nTo add Inno Setup to PATH permanently:" -ForegroundColor Cyan
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

Write-Host "Starting InnoSetup compilation..." -ForegroundColor Yellow
if ($found) {
    $innoCommand = "`"$isccPath`" `"$issPath`""
}
else {
    $innoCommand = "iscc `"$issPath`""
}
Write-Host "Running: $innoCommand" -ForegroundColor Yellow
$innoResult = Invoke-Expression $innoCommand
$innoExitCode = $LASTEXITCODE

if ($innoExitCode -ne 0) {
    Write-Host "InnoSetup compilation failed with exit code: $innoExitCode" -ForegroundColor Red
    exit 1
}
Write-Host "InnoSetup compilation completed successfully." -ForegroundColor Green

# Clean up environment variables
$env:ACCESSIWEATHER_ROOT_DIR = $null
$env:ACCESSIWEATHER_DIST_DIR = $null
$env:ACCESSIWEATHER_VERSION = $null

# Final message
Write-Host "`n===== Build Complete =====" -ForegroundColor Green
Write-Host "Installer: installer\dist\${AppName}_Setup_v${AppVersion}.exe" -ForegroundColor Cyan
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

    # Automatically close processes without asking
    Write-Host "Automatically closing processes started during the build..." -ForegroundColor Yellow
    $newProcesses | ForEach-Object {
        try {
            Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
            Write-Host "Closed process: $($_.ProcessName) (PID: $($_.Id))" -ForegroundColor Green
        }
        catch {
            Write-Host "Failed to close process: $($_.ProcessName) (PID: $($_.Id))" -ForegroundColor Red
        }
    }
}
else {
    Write-Host "No new processes were detected." -ForegroundColor Green
}

# Verify output files
Write-Host "`n===== Verifying output files =====" -ForegroundColor Yellow
$installerPath = "installer\dist\${AppName}_Setup_v${AppVersion}.exe"
$portablePath = "dist\${AppName}_Portable_v${AppVersion}.zip"
$executablePath = "dist\$AppName\$AppName.exe"

$allFilesExist = $true

if (Test-Path $executablePath) {
    Write-Host "[OK] Executable created successfully: $executablePath" -ForegroundColor Green
}
else {
    Write-Host "[ERROR] Executable was not created: $executablePath" -ForegroundColor Red
    $allFilesExist = $false
}

if (Test-Path $installerPath) {
    $installerSize = (Get-Item $installerPath).Length / 1MB
    Write-Host "[OK] Installer created successfully: $installerPath (Size: $($installerSize.ToString("0.00")) MB)" -ForegroundColor Green
}
else {
    Write-Host "[ERROR] Installer was not created: $installerPath" -ForegroundColor Red
    $allFilesExist = $false
}

if (Test-Path $portablePath) {
    $portableSize = (Get-Item $portablePath).Length / 1MB
    Write-Host "[OK] Portable ZIP created successfully: $portablePath (Size: $($portableSize.ToString("0.00")) MB)" -ForegroundColor Green
}
else {
    Write-Host "[ERROR] Portable ZIP was not created: $portablePath" -ForegroundColor Red
    $allFilesExist = $false
}

if ($allFilesExist) {
    Write-Host "`nBuild process completed successfully!" -ForegroundColor Green
}
else {
    Write-Host "`nBuild process completed with errors. Some output files are missing." -ForegroundColor Red
}
