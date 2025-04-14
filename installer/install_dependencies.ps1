# Script to install Python dependencies for AccessiWeather
try {
    Write-Host "Installing required Python packages..."
    pip install -q wxPython requests plyer geopy python-dateutil
    Write-Host "Dependencies installed successfully." -ForegroundColor Green
} 
catch {
    Write-Host "Error installing dependencies. The application may not work correctly." -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
}

# Wait for user to press a key before closing
Write-Host "`nPress any key to continue..." -ForegroundColor Cyan
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
