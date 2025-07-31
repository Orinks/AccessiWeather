# AccessiWeather Migration Guide: wxPython to Toga

This guide helps users transition from the legacy wxPython-based AccessiWeather to the new Toga-based implementation.

## Overview

AccessiWeather has been completely rewritten using the BeeWare/Toga framework to provide:
- Better cross-platform compatibility
- Improved accessibility features
- Modern async-first architecture
- Simplified codebase and maintenance

## What's Changed

### User Interface
- **Same functionality**: All core weather features remain the same
- **Modern look**: Updated UI using native platform controls
- **Better accessibility**: Enhanced screen reader compatibility
- **Keyboard navigation**: Improved keyboard shortcuts and navigation

### Installation & Setup
- **Same installation process**: `pip install -e .` or download binaries
- **Configuration preserved**: Your settings and locations are automatically migrated
- **Same command-line options**: All CLI arguments work the same way

### New Features in Toga Version
- **Enhanced system tray**: Better integration with system notifications
- **Improved error handling**: More user-friendly error messages
- **Better performance**: Async-first architecture for smoother operation
- **Sound pack system**: Customizable notification sounds (new feature)

## Migration Steps

### For Regular Users

1. **Backup your configuration** (optional but recommended):
   ```bash
   # Windows
   copy "%APPDATA%\AccessiWeather\*" "backup_folder"

   # Linux/macOS
   cp -r ~/.config/accessiweather backup_folder
   ```

2. **Install the new version**:
   - Download the latest installer from [GitHub Releases](https://github.com/Orinks/AccessiWeather/releases)
   - Or install from source: `pip install -e .`

3. **Run the application**:
   ```bash
   accessiweather
   ```

4. **Verify your settings**:
   - Your locations should be automatically preserved
   - Check Settings → General to ensure your preferences are correct
   - Test weather alerts and notifications

### For Developers

1. **Update dependencies**:
   ```bash
   pip install toga>=0.5.1
   # wxPython is no longer required
   ```

2. **Use Briefcase for packaging**:
   ```bash
   # Development
   briefcase dev

   # Testing
   briefcase dev --test

   # Building
   briefcase build
   briefcase package
   ```

3. **Update imports** (if extending the codebase):
   ```python
   # Old (wxPython)
   import wx

   # New (Toga)
   import toga
   from toga.style import Pack
   ```

## Key Differences

### Architecture
- **Old**: Complex threading with wx.CallAfter
- **New**: Modern async/await patterns
- **Old**: Multiple service layers
- **New**: Simplified, direct API calls

### Configuration
- **Location**: Same location (`~/.config/accessiweather` or `%APPDATA%\AccessiWeather`)
- **Format**: Same JSON format, fully compatible
- **Migration**: Automatic, no user action required

### Features Removed
- **None**: All features from the wxPython version are preserved
- **Enhanced**: Many features have been improved for better accessibility

### New Features
- **Sound packs**: Customizable notification sounds
- **Better system tray**: Enhanced tray menu and notifications
- **Improved alerts**: Better weather alert management
- **Cross-platform**: Better support for Linux and macOS

## Troubleshooting

### Common Issues

1. **"Application won't start"**:
   - Ensure Python 3.7+ is installed
   - Check that Toga is installed: `pip show toga`
   - Try running with debug mode: `accessiweather --debug`

2. **"Settings not preserved"**:
   - Check if config directory exists
   - Verify file permissions
   - Try portable mode: `accessiweather --portable`

3. **"System tray not working"**:
   - This is platform-dependent
   - Check system tray settings in your OS
   - Try restarting the application

4. **"Keyboard navigation issues"**:
   - Use Tab/Shift+Tab to navigate
   - Press Enter or Space to activate controls
   - Use arrow keys in lists and dropdowns

### Getting Help

- **Issues**: Report bugs on [GitHub Issues](https://github.com/Orinks/AccessiWeather/issues)
- **Discussions**: Join discussions on [GitHub Discussions](https://github.com/Orinks/AccessiWeather/discussions)
- **Documentation**: Check the [User Manual](user_manual.md)

## Benefits of the Migration

### For Users
- **Better performance**: Faster startup and operation
- **Enhanced accessibility**: Improved screen reader support
- **Modern interface**: Native look and feel on each platform
- **Better reliability**: Fewer crashes and better error handling

### For Developers
- **Simpler codebase**: Easier to understand and maintain
- **Modern patterns**: Async/await instead of complex threading
- **Better testing**: Improved test coverage and reliability
- **Cross-platform**: Easier deployment to multiple platforms

## Rollback (If Needed)

If you need to temporarily use the old version:

1. **Install from specific commit**:
   ```bash
   git checkout <last-wxpython-commit>
   pip install -e .
   ```

2. **Use legacy branch** (if available):
   ```bash
   git checkout legacy-wxpython
   pip install -e .
   ```

**Note**: The legacy wxPython version is no longer maintained and may have security or compatibility issues.

## Future Roadmap

- **Mobile support**: Potential iOS/Android versions using BeeWare
- **Web version**: Browser-based version for universal access
- **Enhanced plugins**: Sound pack system expansion
- **Better internationalization**: Multi-language support

## Feedback

We value your feedback on the migration! Please:
- Report any issues you encounter
- Suggest improvements for accessibility
- Share your experience with the new version

The Toga-based AccessiWeather represents the future of the project, providing a solid foundation for continued development and improvement.
