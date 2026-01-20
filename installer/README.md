# AccessiWeather Build System

This directory contains the build system for creating AccessiWeather installers using PyInstaller.

## Quick Start

```bash
# Install build dependencies
pip install pyinstaller pillow

# Generate icons (optional - will be auto-generated if missing)
python installer/create_icons.py

# Full build (app + installer + portable ZIP)
python installer/build.py

# Build app only (no installer)
python installer/build.py --skip-installer
```

## Build Scripts

| Script | Purpose |
|--------|--------|
| `build.py` | Main build script - handles everything |
| `create_icons.py` | Generates weather-themed app icons |
| `accessiweather.spec` | PyInstaller configuration |
| `accessiweather.iss` | Inno Setup script (Windows installer) |

## Build Outputs

All outputs are placed in the `dist/` directory:

### Windows
- `AccessiWeather_Setup_vX.X.X.exe` - Inno Setup installer (MSI alternative)
- `AccessiWeather_Portable_vX.X.X.zip` - Portable version (no install needed)
- `AccessiWeather.exe` - Single-file executable

### macOS
- `AccessiWeather_vX.X.X.dmg` - macOS disk image
- `AccessiWeather.app` - Application bundle

## Requirements

### All Platforms
- Python 3.10+
- PyInstaller (`pip install pyinstaller`)
- Pillow for icon generation (`pip install pillow`)

### Windows (for installer)
- [Inno Setup 6](https://jrsoftware.org/isinfo.php)

### macOS (for DMG)
- `create-dmg` (optional, `brew install create-dmg`)
- Falls back to `hdiutil` if not available

## Build Options

```bash
# Show all options
python installer/build.py --help

# Generate icons only
python installer/build.py --icons-only

# Build without creating installer
python installer/build.py --skip-installer

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

To modify installer behavior, edit `accessiweather.iss`.

## Troubleshooting

### PyInstaller Issues

1. **Missing modules**: Add to `hiddenimports` in `accessiweather.spec`
2. **Large file size**: Add unused packages to `excludes`
3. **Runtime errors**: Check `--debug` build output

### Icon Generation

1. **Pillow not found**: `pip install pillow`
2. **ICNS not supported**: macOS only supports ICNS generation

### Inno Setup

1. **ISCC not found**: Install Inno Setup or add to PATH
2. **Build fails**: Check `accessiweather.iss` syntax

## CI/CD

The GitHub Actions workflow `.github/workflows/pyinstaller-build.yml` automates:

1. Building on Windows and macOS
2. Creating installers (Inno Setup / DMG)
3. Creating portable ZIPs
4. Uploading artifacts
5. Creating releases (on tags)

## Directory Structure

```
installer/
├── README.md              # This file
├── build.py               # Main build script
├── create_icons.py        # Icon generator
├── accessiweather.spec    # PyInstaller spec
├── accessiweather.iss     # Inno Setup script
├── app.ico                # Generated Windows icon
└── make.py                # Legacy Briefcase script (deprecated)
```
