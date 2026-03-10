# GitHub Pages Mirror Setup

> WordPress is now the primary public release page. This document only covers
> the GitHub Pages mirror and nightly.link support.

## ✅ What's Been Implemented

### 1. **nightly.link Verification**
- ✅ Confirmed nightly.link GitHub app is working
- ✅ Tested URLs for dev branch (working with v0.9.3 artifacts)
- ✅ Main branch has no builds yet (expected, since development is on dev)

### 2. **GitHub Pages Site**
- ✅ Enabled GitHub Pages at: https://orinks.github.io/AccessiWeather/
- ✅ Created responsive download page (`docs/index.html`)
- ✅ Added automatic build information updates
- ✅ Configured Jekyll for proper GitHub Pages support

### 3. **CI/CD Integration**
- ✅ Added `update-pages.yml` workflow to automatically update download links
- ✅ Created `test-nightly-link.yml` for testing the integration
- ✅ Existing `build.yml` already has proper artifact naming

### 4. **Download URLs Available**

#### Dev Branch (Currently Working)
- **Preview**: https://nightly.link/Orinks/AccessiWeather/workflows/briefcase-build/dev?preview
- **Installer**: https://nightly.link/Orinks/AccessiWeather/workflows/briefcase-build/dev/windows-installer-0.9.3.zip
- **Portable**: https://nightly.link/Orinks/AccessiWeather/workflows/briefcase-build/dev/windows-portable-0.9.3.zip

#### Main Branch (No builds yet)
- **Preview**: https://nightly.link/Orinks/AccessiWeather/workflows/briefcase-build/main?preview
- **Will work once builds run on main branch**

## 🚀 Next Steps

### 1. **Test the Setup**
Run the test workflow to verify everything is working:
```bash
gh workflow run test-nightly-link.yml -f test_branch=dev
```

### 2. **Trigger a Build on Main Branch**
To get nightly.link working for main branch, you need a successful build:
- Option A: Merge dev to main
- Option B: Manually trigger build workflow on main
- Option C: Push a commit to main

### 3. **Access Your Download Site**
Visit: https://orinks.github.io/AccessiWeather/

The site will automatically:
- Show latest version information
- Provide direct download links
- Update when new builds are available

### 4. **Customize the Site (Optional)**
Edit `docs/index.html` to:
- Update branding/colors
- Add more features/screenshots
- Modify download descriptions

## 📋 How It Works

### Automatic Updates
1. When `build.yml` completes successfully
2. `update-pages.yml` triggers automatically
3. Fetches latest build info from GitHub API
4. Updates `docs/build-info.json` with version/date info
5. Commits changes and deploys to GitHub Pages

### nightly.link URLs
- **Generic**: Always points to latest successful build
- **Specific**: Points to exact version (if you know version number)
- **Preview**: Shows all available artifacts with download links

### User Experience
- No GitHub login required for downloads
- Direct download links work immediately
- Automatic version detection
- Mobile-friendly responsive design

## 🔧 Configuration Files Created

```
docs/
├── index.html              # Main download page
├── _config.yml            # Jekyll configuration
├── README.md              # Documentation
└── nightly-link-setup.md  # This file

.github/workflows/
├── update-pages.yml       # Auto-update GitHub Pages
└── test-nightly-link.yml  # Test nightly.link integration
```

## 🎯 Benefits Achieved

1. **Public Downloads**: No GitHub login required
2. **Always Latest**: URLs automatically point to newest builds
3. **Professional**: Clean, accessible download page
4. **Automated**: No manual intervention needed
5. **Dual Channels**: Separate main (stable) and dev (latest) downloads
6. **Mobile Friendly**: Responsive design works on all devices

## 🐛 Troubleshooting

### If nightly.link URLs return 404:
- Check if builds have run successfully on that branch
- Verify artifact names match expected pattern
- Ensure nightly.link app is installed (✅ already done)

### If GitHub Pages doesn't update:
- Check `update-pages.yml` workflow logs
- Verify GitHub Pages is enabled in repository settings
- Ensure proper permissions are set

### If downloads fail:
- Artifacts expire after 90 days
- Check if builds are still successful
- Verify artifact retention settings in `build.yml`

## 📞 Support

- Test workflows: Use `test-nightly-link.yml`
- Check build status: GitHub Actions tab
- View site: https://orinks.github.io/AccessiWeather/
- nightly.link docs: https://nightly.link/
