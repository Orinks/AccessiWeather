# AccessiWeather Build System

This directory contains the build system for creating AccessiWeather installers using Nuitka.

## Quick Start

```bash
# Install build dependencies
pip install nuitka pillow

# Generate icons (optional - will be auto-generated if missing)
python installer/create_icons.py

# Full Nuitka build (app + installer/portable ZIP where supported)
python installer/build_nuitka.py

# Build app only (no installer)
python installer/build.py --skip-installer
```

## Build Scripts

| Script | Purpose |
|--------|--------|
| `build_nuitka.py` | Production build script used by CI |
| `build.py` | Legacy PyInstaller build script and shared packaging helpers |
| `create_icons.py` | Generates weather-themed app icons |
| `accessiweather.spec` | Legacy PyInstaller configuration |
| `accessiweather.iss` | Inno Setup script (Windows installer) |

## Build Outputs

All outputs are placed in the `dist/` directory:

### Windows
- `AccessiWeather_Setup_vX.X.X.exe` - Inno Setup installer (MSI alternative)
- `AccessiWeather_Portable_vX.X.X.zip` - Portable version (no install needed)
- `AccessiWeather_dir/` - Staged application directory

### macOS
- `AccessiWeather_macOS_vX.X.X.zip` - macOS app ZIP
- `AccessiWeather.app` - Application bundle

## Requirements

### All Platforms
- Python 3.10+
- Nuitka (`pip install nuitka`)
- Pillow for icon generation (`pip install pillow`)

### Windows (for installer)
- [Inno Setup 6](https://jrsoftware.org/isinfo.php)

### macOS (for DMG)
- `create-dmg` (optional, `brew install create-dmg`)
- Falls back to `hdiutil` if not available

## Build Options

```bash
# Show all Nuitka build options
python installer/build_nuitka.py --help

# Generate icons only
python installer/build.py --icons-only

# Build without creating the Windows installer
python installer/build_nuitka.py --skip-installer

# Build without generating icons (use existing)
python installer/build.py --skip-icons

# Clean build artifacts
python installer/build.py --clean

# Run in development mode
python installer/build.py --dev
```

## Icon Generation

Icons are **committed to the repository** and don't need to be regenerated during builds.

The `create_icons.py` script generates weather-themed icons (sun with cloud design):

- **Windows**: `app.ico` (multi-size ICO file)
- **macOS**: `app.icns` (multi-size ICNS file, must be generated on macOS)
- **PNG**: Various sizes for other uses

To regenerate icons (only needed if you want to change the design):
```bash
python installer/create_icons.py
```

## Inno Setup Configuration

The `accessiweather.iss` script creates:
- Start Menu shortcuts
- Desktop shortcut (optional)
- Proper uninstaller
- Per-user installation (no admin required)

Installer scope policy (ARP hardening):
- Default scope is per-user (`PrivilegesRequired=lowest`).
- Upgrades reuse the previous install privilege mode (`UsePreviousPrivileges=yes`) so users stay on one logical install identity.
- Interactive privilege switching is disabled to reduce accidental HKCU/HKLM split installs.
- When running as admin, setup removes stale per-user uninstall keys for AccessiWeather to prevent duplicate Add/Remove Programs entries.

To modify installer behavior, edit `accessiweather.iss`.

## Troubleshooting

### Nuitka Issues

1. **Missing modules**: Add targeted Nuitka include options in `build_nuitka.py`
2. **Large file size**: Check `build/nuitka/compilation-report.xml`
3. **Runtime errors**: Rebuild with Nuitka report output and inspect included modules

### Icon Generation

1. **Pillow not found**: `pip install pillow`
2. **ICNS not supported**: macOS only supports ICNS generation

### Inno Setup

1. **ISCC not found**: Install Inno Setup or add to PATH
2. **Build fails**: Check `accessiweather.iss` syntax

## CI/CD

The GitHub Actions workflow `.github/workflows/build.yml` automates:

1. Building on Windows and macOS
2. Creating installers (Inno Setup / DMG)
3. Creating portable ZIPs
4. Uploading artifacts
5. Creating releases (on tags)

## Directory Structure

```
installer/
├── README.md              # This file
├── build_nuitka.py        # Production Nuitka build script
├── build.py               # Legacy build script and shared packaging helpers
├── create_icons.py        # Icon generator
├── accessiweather.spec    # Legacy PyInstaller spec
├── accessiweather.iss     # Inno Setup script
├── app.ico                # Generated Windows icon
```

## Installer Validation (Windows ARP dedupe)

Use these deterministic smoke checks after generating a setup EXE:

1. Install current build in per-user mode.
2. (Optional) Install an older build in elevated/per-machine mode to simulate mixed scope history.
3. Install the new setup and confirm only one AccessiWeather entry remains in Add/Remove Programs for the active scope.

PowerShell registry checks:

```powershell
$hkcu = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall'
$hklm = 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall'

Get-ChildItem $hkcu, $hklm |
  Where-Object { $_.PSChildName -match 'B8F4D7A2-9E3C-4B5A-8D1F-6C2E7A9B0D3E' } |
  Select-Object PSPath
```

Expected:
- Fresh installs: one uninstall key for AccessiWeather.
- Admin upgrades from mixed history: HKCU stale key removed by installer cleanup.
