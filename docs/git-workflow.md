# AccessiWeather Git Workflow

## 🎯 **Branch Strategy**

### **Dev Branch** (Active Development)
- **Purpose**: Active development and testing
- **GitHub Pages**: ✅ Deploys from here
- **CI/CD**: ✅ Runs on every push
- **Builds**: ✅ Creates nightly.link artifacts
- **Stability**: Unstable, latest features

### **Main Branch** (Releases Only)
- **Purpose**: Stable releases only
- **GitHub Pages**: ❌ No longer deploys from here
- **CI/CD**: ❌ No automatic builds
- **Builds**: ✅ Only for tagged releases
- **Stability**: Stable, production-ready

## 🔄 **Workflow Process**

### **Daily Development**
1. Work on `dev` branch
2. Push changes to `dev`
3. CI runs automatically
4. Build artifacts created
5. GitHub Pages updates automatically
6. nightly.link URLs stay current

### **Creating Releases**
1. When ready for release, merge `dev` → `main`
2. Tag the release on `main` (e.g., `v1.0.0`)
3. Release workflow runs automatically
4. Creates GitHub Release with assets
5. `main` branch stays clean for releases

## 🌐 **GitHub Pages Setup**

**Current Configuration:**
- **Source Branch**: `dev` 
- **Path**: `/docs`
- **URL**: https://orinks.github.io/AccessiWeather/
- **Updates**: Automatically when `dev` branch changes

## 🚀 **CI/CD Workflows**

### **ci.yml** - Code Quality
- **Triggers**: Push/PR to `dev` branch
- **Purpose**: Tests, linting, security scans
- **Runs**: On every dev branch change

### **build.yml** - Build Artifacts  
- **Triggers**: Push to `dev` branch (after CI passes)
- **Purpose**: Creates installer and portable artifacts
- **Artifacts**: Available via nightly.link

### **update-pages.yml** - GitHub Pages
- **Triggers**: After successful builds on `dev`
- **Purpose**: Updates download page with latest build info
- **Updates**: Version numbers, download links

### **release.yml** - Official Releases
- **Triggers**: Push to `main` branch or manual dispatch
- **Purpose**: Creates tagged releases with assets
- **Creates**: GitHub Release with installer/portable

## 📦 **Download Experience**

### **Development Builds** (from dev branch)
- **Access**: https://orinks.github.io/AccessiWeather/
- **Updates**: Automatically with every dev build
- **Stability**: Latest features, may be unstable
- **URLs**: nightly.link direct downloads

### **Stable Releases** (from main branch)
- **Access**: GitHub Releases page
- **Updates**: Manual, when you create releases
- **Stability**: Tested, production-ready
- **URLs**: GitHub Release assets

## 🎯 **Benefits of This Setup**

### ✅ **Clear Separation**
- Dev = unstable, latest features
- Main = stable, releases only

### ✅ **Automatic Updates**
- GitHub Pages always shows latest dev builds
- No manual intervention needed

### ✅ **Professional Releases**
- Main branch reserved for quality releases
- Tagged releases with proper versioning

### ✅ **User Choice**
- Users can access bleeding-edge (dev) or stable (releases)
- Clear distinction between development and production

## 🔧 **Commands for Releases**

### **Creating a Release**
```bash
# 1. Ensure dev is ready for release
git checkout dev
git push origin dev

# 2. Merge to main (when ready for release)
git checkout main
git merge dev --no-ff -m "Release v1.0.0"
git tag v1.0.0
git push origin main --tags

# 3. Release workflow runs automatically
```

### **Hotfix Process**
```bash
# 1. Create hotfix branch from main
git checkout main
git checkout -b hotfix/critical-fix

# 2. Make fix and test
# ... make changes ...
git commit -m "Fix critical issue"

# 3. Merge to both main and dev
git checkout main
git merge hotfix/critical-fix
git tag v1.0.1
git push origin main --tags

git checkout dev  
git merge hotfix/critical-fix
git push origin dev

# 4. Delete hotfix branch
git branch -d hotfix/critical-fix
```

## 📋 **Summary**

This workflow gives you:
- **Dev branch**: Active development with automatic GitHub Pages
- **Main branch**: Clean, release-only branch
- **Automatic builds**: On dev for testing
- **Manual releases**: On main for production
- **Best practices**: Industry-standard Git workflow

Your users get the best of both worlds - access to latest features via GitHub Pages (dev) and stable releases via GitHub Releases (main).
