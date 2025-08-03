# AccessiWeather TUF Update Repository

This directory contains the TUF (The Update Framework) repository setup for AccessiWeather secure updates.

## Quick Start

### 1. Install Dependencies

```bash
# Activate virtual environment
.\.venv\Scripts\activate

# Install tufup
pip install tufup>=0.12.0
```

### 2. Initialize Repository (One-time setup)

```bash
cd tuf_repo
python repo_init.py
```

This creates:
- `keystore/` - Private signing keys (KEEP SECURE!)
- `repository/metadata/` - TUF metadata files
- `repository/targets/` - Application archives and patches

### 3. Build and Add First Version

```bash
# Build with Briefcase
cd ..
briefcase package

# Add to TUF repository
cd tuf_repo
python repo_add_bundle.py 0.9.4
```

### 4. Upload to orinks.net

Upload the `repository/` directory to `orinks.net/updates/`:

```bash
# Example using rsync (adjust paths as needed)
rsync -av repository/ user@orinks.net:/path/to/public_html/updates/
```

### 5. Include Root Metadata in App

Copy `repository/metadata/root.json` to your app's resources so it can be bundled:

```bash
# Copy root.json to be included in Briefcase build
cp repository/metadata/root.json ../src/accessiweather/resources/
```

## Adding New Versions

```bash
# Build new version
briefcase package

# Add to repository
python repo_add_bundle.py 0.9.5

# Upload to server
rsync -av repository/ user@orinks.net:/path/to/public_html/updates/
```

## Repository Structure

```
tuf_repo/
├── keystore/              # Private keys (NEVER upload to server)
│   ├── root_key.json
│   ├── targets_key.json
│   ├── snapshot_key.json
│   └── timestamp_key.json
├── repository/            # Upload this directory to orinks.net/updates/
│   ├── metadata/
│   │   ├── root.json      # Include this in your app bundle
│   │   ├── targets.json
│   │   ├── snapshot.json
│   │   └── timestamp.json
│   └── targets/
│       ├── accessiweather-0.9.4.tar.gz
│       ├── accessiweather-0.9.5.tar.gz
│       └── accessiweather-0.9.4-to-0.9.5.patch
├── repo_init.py           # Initialize repository
├── repo_add_bundle.py     # Add new versions
└── repo_settings.py       # Configuration
```

## Security Notes

⚠️ **CRITICAL**: Never upload the `keystore/` directory to your web server or version control!

✅ **DO**:
- Keep `keystore/` backed up securely
- Only upload `repository/` directory to web server
- Include `root.json` in your application bundle
- Use HTTPS for your update server

❌ **DON'T**:
- Upload private keys to server
- Commit keys to version control
- Share keys via insecure channels

## Configuration

Edit `repo_settings.py` to customize:
- Repository paths
- Update server URLs
- Key thresholds
- Expiration times

## Troubleshooting

### "TUF root metadata not found"
- Make sure `root.json` is included in your app bundle
- Check that the client can find the metadata directory

### "Failed to initialize TUF client"
- Verify tufup is installed: `pip install tufup`
- Check that repository structure is correct
- Ensure HTTPS is working on update server

### "No updates available"
- Verify repository is uploaded to correct URL
- Check version numbering (must be PEP440 compliant)
- Ensure metadata is properly signed

## Testing Updates Locally

```bash
# Serve repository locally for testing
cd repository
python -m http.server 8000

# Update app configuration to use localhost
# metadata_base_url = "http://localhost:8000/metadata/"
# target_base_url = "http://localhost:8000/targets/"
```

## Production Deployment

1. **Build and test locally**
2. **Upload repository/ to orinks.net/updates/**
3. **Update app configuration to use production URLs**
4. **Test update process with production server**
5. **Announce new version to users**

## Support

For issues with TUF setup:
- Check [tufup documentation](https://github.com/dennisvang/tufup)
- Review [TUF specification](https://theupdateframework.io/)
- Test with local HTTP server first