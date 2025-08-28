# AccessiWeather Update System Guide

AccessiWeather features a sophisticated dual-channel update system that provides both maximum security for stable releases and rapid access to beta features for testers.

## 🔄 Update Channels

### 🔒 Stable Channel
- **Purpose**: Production-ready releases for all users
- **Security**: Maximum security with TUF (The Update Framework) cryptographic verification
- **Frequency**: Monthly or as needed for critical fixes
- **Recommended for**: All users who want a reliable, tested experience

### 🧪 Beta Channel
- **Purpose**: Pre-release testing versions
- **Features**: New features before they reach stable release
- **Frequency**: Weekly or bi-weekly
- **Recommended for**: Users who want to try new features and help with testing
- **Note**: May contain bugs, but generally stable for daily use

### 🛠️ Development Channel
- **Purpose**: Latest development builds
- **Features**: Cutting-edge features, immediate bug fixes
- **Frequency**: As needed, potentially daily
- **Recommended for**: Developers, advanced users, and early adopters
- **Warning**: May be unstable, use with caution

## 🔧 Update Methods

### 🔄 Automatic (Recommended)
- **Stable Channel**: Uses TUF for maximum security
- **Beta/Dev Channels**: Uses GitHub for faster deployment
- **Benefits**: Best of both worlds - security for stable, speed for testing

### 🔐 TUF Only
- **Security**: Maximum security with cryptographic verification
- **Limitation**: Only stable releases available
- **Use Case**: High-security environments, production systems

### 📦 GitHub Only
- **Availability**: All release channels available
- **Security**: Standard GitHub security (HTTPS)
- **Use Case**: Beta testing, when TUF is not available

## ⚙️ Configuring Updates

### In-App Configuration

1. **Open Settings**:
   - Press `Alt+S` or
   - Go to File → Settings

2. **Navigate to Updates Tab**:
   - Click on the "Updates" tab

3. **Configure Your Preferences**:
   - **Update Channel**: Choose your desired channel
   - **Update Method**: Select automatic (recommended) or specific method
   - **Auto-check**: Enable for automatic update notifications
   - **Check Interval**: Set how often to check (1-168 hours)

4. **Test Configuration**:
   - Click "Check for Updates Now" to test your settings

### Settings Explained

#### Update Channel Options
- `Stable (Production releases only)` - Most reliable
- `Beta (Pre-release testing)` - New features, some bugs expected
- `Development (Latest features, may be unstable)` - Cutting edge, use with caution

#### Update Method Options
- `Automatic (TUF for stable, GitHub for beta/dev)` - Recommended for most users
- `TUF Only (Secure, stable releases only)` - Maximum security, stable only
- `GitHub Only (All releases, less secure)` - All channels, standard security

## 🔍 Checking for Updates

### Automatic Checks
- Enabled by default
- Runs in background at configured interval
- Shows notification when updates are available
- Respects your channel and method preferences

### Manual Checks
- Go to Settings → Updates tab
- Click "Check for Updates Now"
- Immediately checks using current configuration
- Shows results in the settings dialog

## 📥 Installing Updates

### Automatic Installation (Future Feature)
- Currently in development
- Will support seamless background updates
- Will respect user preferences for update timing

### Manual Installation (Current)
1. **Download**: Click download link in update notification
2. **Install**: Run the downloaded installer
3. **Restart**: Restart AccessiWeather to use new version

## 🛡️ Security Features

### TUF (The Update Framework)
- **Cryptographic Verification**: All stable releases are cryptographically signed
- **Rollback Protection**: Prevents downgrade attacks
- **Compromise Resilience**: Multiple keys required for malicious updates
- **Metadata Security**: Update metadata is also signed and verified

### GitHub Releases
- **HTTPS Security**: All downloads use encrypted connections
- **GitHub Security**: Relies on GitHub's security infrastructure
- **Checksums**: Release assets include SHA256 checksums for verification

## 🔧 Troubleshooting

### Update Check Fails
1. **Check Internet Connection**: Ensure you have internet access
2. **Check Firewall**: Make sure AccessiWeather can access the internet
3. **Try Different Method**: Switch from TUF to GitHub or vice versa
4. **Check Logs**: Enable debug mode for detailed error information

### TUF Not Available
- **Cause**: TUF dependencies not installed or system incompatibility
- **Solution**: Update method automatically falls back to GitHub
- **Manual Fix**: Install tufup package: `pip install tufup`

### No Updates Found
- **Stable Channel**: You may already have the latest stable version
- **Beta Channel**: No new beta releases since your version
- **Check Version**: Verify your current version in Help → About

### Download Fails
1. **Retry**: Try the download again
2. **Check Space**: Ensure sufficient disk space
3. **Manual Download**: Download directly from GitHub releases page
4. **Contact Support**: Report persistent download issues

## 📊 Update Information

### Platform Information
The Updates tab shows:
- **Platform**: Your operating system and architecture
- **Deployment**: How AccessiWeather was installed (installer, portable, etc.)
- **Update Capability**: Whether your installation supports updates

### Version Information
- **Current Version**: Your installed version
- **Available Version**: Latest version for your channel
- **Release Notes**: What's new in the available update

## 🎯 Best Practices

### For Regular Users
- **Use Stable Channel**: Most reliable experience
- **Enable Auto-check**: Stay informed about updates
- **Use Automatic Method**: Best security and convenience

### For Beta Testers
- **Use Beta Channel**: Get new features early
- **Check More Frequently**: Set 12-hour check interval
- **Report Issues**: Help improve AccessiWeather by reporting bugs

### For Developers
- **Use Development Channel**: Get latest changes immediately
- **Enable Debug Mode**: Get detailed logging information
- **Frequent Checks**: Set 6-hour check interval or check manually

## 🔗 Related Resources

- **Beta Testing Guide**: `BETA_TESTING.md`
- **Release Channels Guide**: `update_channels.md`
- **GitHub Releases**: https://github.com/joshuakitchen/accessiweather/releases
- **TUF Project**: https://theupdateframework.io/

## 📞 Support

If you encounter issues with the update system:

1. **Check This Guide**: Review troubleshooting section
2. **Enable Debug Mode**: Get detailed error information
3. **GitHub Issues**: Report bugs at https://github.com/joshuakitchen/accessiweather/issues
4. **Include Information**: Provide your platform, version, and error details

---

*Last updated: December 2024*
