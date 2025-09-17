# AccessiWeather Beta Testing Guide

Welcome to the AccessiWeather beta testing program! This guide will help you get set up to receive and test pre-release versions of AccessiWeather.

## 🎯 What is Beta Testing?

Beta testing allows you to:
- ✅ Try new features before they're released to everyone
- ✅ Help identify bugs and issues
- ✅ Provide feedback on accessibility and usability
- ✅ Shape the future of AccessiWeather

## 🚀 Getting Started

### Configuring Beta Updates in AccessiWeather

1. **Open AccessiWeather**
2. **Go to Settings** (Alt+S or from the File menu)
3. **Click on the "Updates" tab**
4. **Configure your update preferences**:
   - **Update Channel**: Select `Beta (Pre-release testing)`
   - **Update Method**: Choose `Automatic (TUF for stable, GitHub for beta/dev)` (recommended)
   - **Check for updates automatically**: Enable this option
   - **Check Interval**: Set to `12 hours` for more frequent beta updates
5. **Click "OK"** to save your settings
6. **Test the configuration** by clicking "Check for Updates Now"

### Understanding Update Channels

- **🔒 Stable**: Production releases only, maximum security with TUF verification
- **🧪 Beta**: Pre-release versions for testing, includes new features before stable release
- **🛠️ Development**: Latest development builds, cutting-edge features but may be unstable

## 📦 Types of Beta Releases

### Beta Releases (`v1.0.0-beta.1`)
- **Stability**: Mostly stable, some bugs expected
- **Frequency**: Weekly or bi-weekly
- **Purpose**: Feature testing and bug hunting

### Alpha Releases (`v1.0.0-alpha.1`)
- **Stability**: Less stable, more experimental
- **Frequency**: As needed for major features
- **Purpose**: Early feature testing

### Release Candidates (`v1.0.0-rc.1`)
- **Stability**: Very stable, final testing
- **Frequency**: Before major releases
- **Purpose**: Final validation before stable release

### Development Builds (`v1.0.0-dev.20241224`)
- **Stability**: Potentially unstable
- **Frequency**: As needed
- **Purpose**: Testing specific fixes or features

## 🧪 How to Test Beta Releases

### When You Receive a Beta Update

1. **Read the Release Notes**
   - Check what's new or changed
   - Look for known issues
   - Note any special testing instructions

2. **Install the Update**
   - Download from GitHub Releases
   - Install over your existing version
   - Or use the portable version for side-by-side testing

3. **Test Core Functionality**
   - [ ] Application starts without errors
   - [ ] Location search works
   - [ ] Current weather displays correctly
   - [ ] Forecasts load properly
   - [ ] Weather alerts function
   - [ ] Settings can be changed and saved

4. **Test Accessibility**
   - [ ] Screen reader compatibility (NVDA, JAWS, Narrator)
   - [ ] Keyboard navigation works
   - [ ] All controls are properly labeled
   - [ ] Focus management is correct

5. **Test New Features**
   - Focus on any new features mentioned in release notes
   - Try different scenarios and edge cases
   - Test with various locations (US and international)

## 🐛 Reporting Issues

### Where to Report
- **GitHub Issues**: https://github.com/joshuakitchen/accessiweather/issues
- **Use the "bug" label** for bugs
- **Use the "beta-feedback" label** for general feedback

### What to Include in Bug Reports

```markdown
**Beta Version**: v1.0.0-beta.1
**Operating System**: Windows 11
**Screen Reader**: NVDA 2024.1 (if applicable)

**Description**:
Brief description of the issue

**Steps to Reproduce**:
1. Step one
2. Step two
3. Step three

**Expected Behavior**:
What should have happened

**Actual Behavior**:
What actually happened

**Additional Context**:
- Error messages (if any)
- Screenshots (if helpful)
- Log files (if available)
```

### Priority Levels
- 🔴 **Critical**: App crashes, data loss, security issues
- 🟡 **High**: Major features broken, accessibility issues
- 🟢 **Medium**: Minor bugs, usability improvements
- 🔵 **Low**: Cosmetic issues, nice-to-have features

## 📋 Beta Testing Checklist

Use this checklist for each beta release:

### Basic Functionality
- [ ] Application launches successfully
- [ ] No crash on startup
- [ ] Main window displays correctly
- [ ] Menu items are accessible

### Weather Features
- [ ] Location search works
- [ ] Current conditions display
- [ ] Hourly forecast loads
- [ ] Extended forecast loads
- [ ] Weather alerts (if available)
- [ ] Multiple locations support

### Accessibility
- [ ] Screen reader announces all content
- [ ] Keyboard navigation works
- [ ] Tab order is logical
- [ ] All buttons/controls are labeled
- [ ] Focus indicators are visible
- [ ] No accessibility regressions

### Settings & Configuration
- [ ] Settings dialog opens
- [ ] All settings can be changed
- [ ] Settings are saved correctly
- [ ] Settings persist after restart
- [ ] Update settings work

### System Integration
- [ ] System tray icon appears
- [ ] Notifications work
- [ ] Auto-start functionality
- [ ] File associations (if any)

## 🎉 Beta Tester Benefits

As a beta tester, you get:
- 🚀 **Early Access** to new features
- 🗣️ **Direct Input** on development decisions
- 🏆 **Recognition** in release notes (if desired)
- 🤝 **Community** access to beta tester discussions

## 📞 Getting Help

### Beta Tester Resources
- **GitHub Discussions**: For questions and feedback
- **GitHub Issues**: For bug reports
- **Email**: [Your contact email] for urgent issues

### Switching Back to Stable
If you need to switch back to stable releases:

1. **Open AccessiWeather Settings** (Alt+S)
2. **Go to the "Updates" tab**
3. **Change Update Channel** to `Stable (Production releases only)`
4. **Click "OK"** to save
5. Wait for the next stable release, or check for updates manually

## 🙏 Thank You!

Your participation in beta testing helps make AccessiWeather better for everyone. Every bug report, suggestion, and piece of feedback contributes to a more accessible and reliable weather application.

**Happy Testing!** 🌤️

---

*Last updated: December 2024*
