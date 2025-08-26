# GitHub App Setup for AccessiWeather

AccessiWeather uses environment variables to securely load GitHub App credentials for sound pack submission functionality. This approach keeps sensitive credentials out of the source code while making them easily accessible to the application.

## Quick Setup

1. **Ensure you have the credentials file**:
   - Make sure `AccessiBotApp Configuration.txt` exists in the project root
   - This file contains the GitHub App ID, Installation ID, and Private Key

2. **Run the setup script**:
   ```bash
   python setup_github_env.py
   ```

3. **Use the generated script** (for future sessions):
   - **Windows**: Run `set_github_env.bat` before starting AccessiWeather
   - **Linux/Mac**: Run `source set_github_env.sh` before starting AccessiWeather

## Environment Variables

The following environment variables are used:

- `ACCESSIWEATHER_GITHUB_APP_ID` - The GitHub App ID (numeric)
- `ACCESSIWEATHER_GITHUB_APP_INSTALLATION_ID` - The Installation ID (numeric)
- `ACCESSIWEATHER_GITHUB_APP_PRIVATE_KEY` - The complete RSA private key in PEM format

## How It Works

1. **Automatic Loading**: When AccessiWeather starts, it automatically checks for these environment variables
2. **Fallback Behavior**: If environment variables are not set, the app falls back to empty credentials (sound pack submission will be disabled)
3. **No User Configuration**: Users don't need to manually configure GitHub App settings - it's handled automatically via environment variables

## Security Features

✅ **Credentials never stored in source code**
✅ **Environment setup scripts are gitignored**
✅ **Credentials file is gitignored**
✅ **Automatic fallback if credentials unavailable**

## Development Workflow

### For Development
```bash
# Set up environment variables
python setup_github_env.py

# Run AccessiWeather (credentials automatically loaded)
python -m accessiweather
```

### For Production/Distribution
Set the environment variables in your deployment environment:

```bash
# Linux/Mac
export ACCESSIWEATHER_GITHUB_APP_ID="1842273"
export ACCESSIWEATHER_GITHUB_APP_INSTALLATION_ID="82746401"
export ACCESSIWEATHER_GITHUB_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----
...
-----END RSA PRIVATE KEY-----"

# Windows
set "ACCESSIWEATHER_GITHUB_APP_ID=1842273"
set "ACCESSIWEATHER_GITHUB_APP_INSTALLATION_ID=82746401"
set "ACCESSIWEATHER_GITHUB_APP_PRIVATE_KEY=-----BEGIN RSA PRIVATE KEY-----..."
```

## Troubleshooting

### Sound Pack Submission Not Working
1. Check if environment variables are set:
   ```bash
   echo $ACCESSIWEATHER_GITHUB_APP_ID  # Linux/Mac
   echo %ACCESSIWEATHER_GITHUB_APP_ID%  # Windows
   ```

2. Re-run the setup script:
   ```bash
   python setup_github_env.py
   ```

3. Verify the credentials file exists and is readable

### Environment Variables Not Persisting
- Environment variables are session-specific
- Use the generated batch/shell scripts for persistent setup
- For permanent setup, add to your shell profile (.bashrc, .zshrc, etc.)

## Files

- `setup_github_env.py` - Setup script (tracked in git)
- `AccessiBotApp Configuration.txt` - Credentials file (gitignored)
- `set_github_env.bat` - Windows environment script (gitignored)
- `set_github_env.sh` - Unix environment script (gitignored)

## Implementation Details

The environment variable loading is implemented in `src/accessiweather/models.py`:

- `AppSettings._load_github_app_from_env()` - Loads credentials from environment
- Called automatically in `AppSettings.from_dict()` and `AppConfig.default()`
- Only loads from environment if current values are empty (respects user configuration)
