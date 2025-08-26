# GitHub App Setup for AccessiWeather

AccessiWeather uses a hybrid approach for GitHub App credentials that provides security during development and seamless user experience in distribution:

- **Development**: Uses environment variables for security
- **Distribution**: Credentials are automatically embedded during build process
- **End Users**: No configuration required - credentials are built into the app

## For End Users

**No setup required!** When you download AccessiWeather, the GitHub App credentials are already embedded in the application. Sound pack submission will work automatically.

## For Developers

### Development Setup

1. **Ensure you have the credentials file**:
   - Make sure `AccessiBotApp Configuration.txt` exists in the project root
   - This file contains the GitHub App ID, Installation ID, and Private Key

2. **Set up environment variables** (for development):
   ```bash
   python setup_github_env.py
   ```

3. **Use the generated script** (for future development sessions):
   - **Windows**: Run `set_github_env.bat` before starting AccessiWeather
   - **Linux/Mac**: Run `source set_github_env.sh` before starting AccessiWeather

## Environment Variables

The following environment variables are used:

- `ACCESSIWEATHER_GITHUB_APP_ID` - The GitHub App ID (numeric)
- `ACCESSIWEATHER_GITHUB_APP_INSTALLATION_ID` - The Installation ID (numeric)
- `ACCESSIWEATHER_GITHUB_APP_PRIVATE_KEY` - The complete RSA private key in PEM format

## How It Works

### For End Users (Distribution)
1. **Build-Time Embedding**: During the build process, GitHub App credentials are automatically embedded into the application
2. **No Configuration**: Users download a fully configured app with credentials already included
3. **Seamless Experience**: Sound pack submission works immediately without any setup

### For Developers
1. **Environment Variables**: Development uses environment variables for security
2. **Build Hooks**: Briefcase automatically embeds credentials during packaging
3. **Automatic Restoration**: Original source files are restored after build to prevent credential leakage

## Security Features

✅ **Credentials never stored in source code** (development)
✅ **Build-time embedding only** (distribution)
✅ **Automatic restoration after build** (prevents source code leakage)
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

**Automatic Build Process**: Credentials are automatically embedded during Briefcase packaging:

```bash
# Build with automatic credential embedding
briefcase build windows    # Credentials embedded automatically
briefcase package windows  # Create installer with embedded credentials
```

**Manual Embedding** (if needed):
```bash
# Embed credentials manually
python scripts/embed_credentials.py

# Build your app
briefcase build windows

# Restore original files
python scripts/embed_credentials.py restore
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
