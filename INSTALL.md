# AccessiWeather Installation Guide

This guide provides detailed instructions for installing and setting up AccessiWeather on your system.

## Prerequisites

- Python 3.7+ (Python 3.11 recommended)
- pip (Python package installer)
- Git (for cloning the repository)

## Installation Steps

### 1. Clone the Repository

```bash
git clone https://github.com/Orinks/AccessiWeather.git
cd AccessiWeather
```

### 2. Install the Package

Install the package:

```bash
pip install -e .
```

This will install AccessiWeather and all its dependencies.

### 3. First-time Setup

Run the application once to create the configuration directory:

```bash
accessiweather
```

The application will prompt you to enter your contact information for the NOAA API.

### 4. Manual Configuration (Optional)

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
