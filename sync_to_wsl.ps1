# Sync BMAD and project files from Windows to WSL
# Run this in PowerShell on Windows

# Configuration - ADJUST THESE PATHS!
$WindowsProject = "C:\Users\$env:USERNAME\accessiweather"
$WSLProject = "\\wsl.localhost\Ubuntu\home\josh\accessiweather"

Write-Host "Syncing from Windows to WSL..." -ForegroundColor Cyan
Write-Host "Source: $WindowsProject"
Write-Host "Target: $WSLProject"

# Check if WSL path is accessible
if (!(Test-Path $WSLProject)) {
    Write-Host "ERROR: WSL path not accessible!" -ForegroundColor Red
    Write-Host "Make sure WSL is running: wsl" -ForegroundColor Yellow
    exit 1
}

# Sync .bmad folder
Write-Host "`nSyncing .bmad folder..." -ForegroundColor Green
robocopy "$WindowsProject\.bmad" "$WSLProject\.bmad" /MIR /XD ".bmad-user-memory" /XF "*.pyc" /R:1 /W:1 /NFL /NDL

# Sync source code
Write-Host "`nSyncing source files..." -ForegroundColor Green
robocopy "$WindowsProject\src" "$WSLProject\src" /MIR /XD "__pycache__" "venv" ".venv" /XF "*.pyc" /R:1 /W:1 /NFL /NDL

# Sync docs
Write-Host "`nSyncing docs..." -ForegroundColor Green
robocopy "$WindowsProject\docs" "$WSLProject\docs" /MIR /R:1 /W:1 /NFL /NDL

# Sync config files
Write-Host "`nSyncing config files..." -ForegroundColor Green
Copy-Item "$WindowsProject\pyproject.toml" "$WSLProject\" -Force
Copy-Item "$WindowsProject\.gitignore" "$WSLProject\" -Force

Write-Host "`n✅ Sync complete!" -ForegroundColor Green
Write-Host ""
Write-Host "To test in WSL:"
Write-Host "1. wsl"
Write-Host "2. cd ~/accessiweather"
Write-Host "3. briefcase dev"
