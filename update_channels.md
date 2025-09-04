# AccessiWeather Update Channels Configuration

## Channel Overview

### Stable Channel (GitHub)
- **Method**: `github`
- **Channel**: `stable`
- **Repository**: `orinks/accessiweather`
- **Audience**: All users
- **Security**: GitHub security with HTTPS
- **Frequency**: Major releases only

### Beta Channel (GitHub)
- **Method**: `github`
- **Channel**: `beta`
- **Repository**: `orinks/accessiweather`
- **Audience**: Beta testers
- **Frequency**: Weekly/bi-weekly

### Development Channel (GitHub)
- **Method**: `github`
- **Channel**: `dev`
- **Repository**: `orinks/accessiweather`
- **Audience**: Developers and early testers
- **Frequency**: As needed

## User Configuration

Users can switch channels through the application settings interface:

### In-App Settings (Recommended)
1. Open AccessiWeather
2. Go to Settings (Ctrl+S or File → Settings)
3. Click on the "Updates" tab
4. Select desired update channel:
   - **Stable (Production releases only)** - For most users
   - **Beta (Pre-release testing)** - For beta testers
   - **Development (Latest features, may be unstable)** - For developers
5. Update method is automatically set to GitHub (All releases)
6. Click "OK" to save settings

### Programmatic Configuration (Advanced)
```python
# For beta testers
update_service.update_settings(
    method="github",
    channel="beta",
    repo_owner="orinks",
    repo_name="accessiweather"
)

# For stable users
update_service.update_settings(
    method="github",
    channel="stable",
    repo_owner="orinks",
    repo_name="accessiweather"
)
```

## Version Naming Convention

### Stable Releases
- Format: `v1.0.0`, `v1.1.0`, `v2.0.0`
- GitHub: Not marked as pre-release
- Deployment: GitHub-only

### Beta Releases
- Format: `v1.0.0-beta.1`, `v1.1.0-beta.2`
- GitHub: Marked as pre-release
- Deployment: GitHub-only

### Development Releases
- Format: `v1.0.0-dev.20241224`, `v1.1.0-alpha.1`
- GitHub: Marked as pre-release
- Deployment: GitHub-only

## Release Process

### For All Releases (GitHub)
1. Update version in `pyproject.toml` and `version.py`
2. Create git tag: `git tag v1.0.0` (stable) or `git tag v1.0.0-beta.1` (beta/dev)
3. Push tag: `git push origin v1.0.0`
4. GitHub Actions automatically builds and creates release

## Testing Updates

### In-App Testing
1. **Configure Settings**: Set your desired channel and method in Settings → Updates
2. **Manual Check**: Click "Check for Updates Now" in the Updates tab
3. **Review Results**: Check the status and available updates
4. **Download and Test**: Follow the download link if updates are available

### Beta Tester Instructions
1. **Enable Beta Channel**: Go to Settings → Updates → Select "Beta (Pre-release testing)"
2. **Set Auto-check**: Enable automatic update checking with 12-hour interval
3. **Test Updates**: Download and test pre-release versions when available
4. **Report Issues**: Submit feedback on GitHub Issues page

### Local Testing (Advanced)
```bash
# Test GitHub updates programmatically
python -c "
from accessiweather.services import GitHubUpdateService
import asyncio

async def test():
    service = GitHubUpdateService()
    service.update_settings(method='github', channel='beta')
    update = await service.check_for_updates()
    print(f'Update available: {update}')

asyncio.run(test())
"
```

## Automation Opportunities

### Automatic Beta Releases
- Trigger on push to `develop` branch
- Create pre-release with timestamp
- Notify beta testers via email/Discord

### Scheduled Stable Releases
- Monthly stable releases from `main` branch
- Automatic GitHub deployment
- Release notes generation from changelog
