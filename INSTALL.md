# AccessiWeather Installation Guide

This guide provides detailed instructions for installing and setting up AccessiWeather on your system.

## Installing a Release (Recommended)

Download the latest release from the [releases page](https://github.com/Orinks/AccessiWeather/releases):

- **Windows**: run `AccessiWeather-<version>-windows-setup.exe`, or unzip the portable build.
- **macOS**: open `AccessiWeather-<version>-macOS.zip` and drag the app to Applications.
- **Linux (any popular distro — Fedora, Ubuntu, Arch, openSUSE, Mint, etc.)**: download
  `AccessiWeather-<version>-linux-x86_64.AppImage`, mark it executable, and run it:

  ```bash
  chmod +x AccessiWeather-*-linux-x86_64.AppImage
  ./AccessiWeather-*-linux-x86_64.AppImage
  ```

  No installation is required. If your distro doesn't ship FUSE and the AppImage won't
  start, run it with `--appimage-extract-and-run`.
- **Linux (Ubuntu/Debian only)**: alternatively, `AccessiWeather-<version>-linux.tar.gz`
  unpacks to a folder containing the `AccessiWeather` executable. This build relies on
  Ubuntu system libraries; on other distros, use the AppImage instead.

## Installing from Source

### Prerequisites

- Python 3.7+ (Python 3.11 recommended)
- pip (Python package installer)
- Git (for cloning the repository)

### Installation Steps

#### 1. Clone the Repository

```bash
git clone https://github.com/Orinks/AccessiWeather.git
cd AccessiWeather
```

#### 2. Install the Package

Install the package:

```bash
pip install -e .
```

This will install AccessiWeather and all its dependencies.

#### 3. First-time Setup

Run the application once to create the configuration directory:

```bash
accessiweather
```

The application will prompt you to enter your contact information for the NOAA API.

#### 4. Manual Configuration (Optional)

If you prefer to set up the configuration manually:

1. Create the configuration directory:
   - Windows: `%USERPROFILE%\.accessiweather`
   - Linux/macOS: `~/.accessiweather`

2. Copy the sample configuration file:
   ```bash
   cp config.sample.json ~/.accessiweather/config.json
   ```

3. Edit the configuration file to add your contact information and customize settings.

## Troubleshooting

### wxPython Installation Issues

If you encounter issues installing wxPython:

#### Windows
```bash
pip install -U wxPython==4.2.2
```

#### Ubuntu/Debian
```bash
sudo apt-get update
sudo apt-get install -y libgtk-3-dev libnotify-dev libsdl2-2.0-0 libtiff5-dev libjpeg-dev
pip install -U wxPython==4.2.2
```

#### macOS
```bash
pip install -U wxPython==4.2.2
```

### Configuration Issues

If the application fails to start due to configuration issues:

1. Check that the configuration directory exists
2. Verify that `config.json` is properly formatted
3. Ensure your contact information is set in the API settings

## Verifying Installation

To verify your installation, run the application and check that it starts correctly:

```bash
accessiweather
```

## Getting Help

If you encounter any issues during installation, please:

1. Check the [GitHub Issues](https://github.com/Orinks/AccessiWeather/issues) for similar problems
2. Create a new issue with details about your system and the error messages
