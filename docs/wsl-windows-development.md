# Cross-Platform Development: WSL ↔ Windows

This guide explains how to develop AccessiWeather in WSL while testing on native Windows.

## Quick Start: One-Time Setup

### Step 1: Choose Your Windows Project Location

Decide where your Windows copy will live:
```
C:\Users\YourName\accessiweather
```

### Step 2: Initial Sync from WSL to Windows

**Option A: Use the sync script (Recommended)**

1. Edit `sync_to_windows.sh` and update this line:
   ```bash
   WINDOWS_PROJECT="/mnt/c/Users/YourName/accessiweather"
   ```

2. Run the sync:
   ```bash
   cd ~/accessiweather
   ./sync_to_windows.sh
   ```

**Option B: Copy directly via Windows Explorer**

1. From WSL, get the Windows path:
   ```bash
   wslpath -w ~/accessiweather
   # Example output: \\wsl.localhost\Ubuntu\home\josh\accessiweather
   ```

2. In Windows Explorer:
   - Press `Win+R`
   - Paste the path above
   - Copy the entire folder to `C:\Users\YourName\accessiweather`

**Option C: Use Git (Best for teams)**

```bash
# In WSL
cd ~/accessiweather
git add .bmad/ docs/ src/
git commit -m "Add BMAD workflow system"
git push

# In Windows PowerShell
cd C:\Users\YourName
git clone https://github.com/yourname/accessiweather.git
cd accessiweather
git checkout dev
```

## Development Workflow

### Recommended: Develop in WSL, Test in Windows

**Daily workflow:**

1. **Code in WSL** (fast, Linux-native tools)
   ```bash
   cd ~/accessiweather
   # Make your changes with your favorite editor
   ruff check --fix . && ruff format .
   pytest -v
   ```

2. **Sync to Windows** (quick, automated)
   ```bash
   ./sync_to_windows.sh
   ```

3. **Test in Windows** (native environment)
   ```powershell
   cd C:\Users\YourName\accessiweather
   briefcase dev
   # Test screen readers, native UI, etc.
   ```

4. **Sync back if needed** (optional, if you made changes in Windows)
   ```powershell
   .\sync_to_wsl.ps1
   ```

### Alternative: Work Directly on Windows Path

You can work directly on Windows filesystem from WSL:

```bash
# In WSL, work on the Windows copy
cd /mnt/c/Users/YourName/accessiweather

# Develop normally
code .  # VS Code
vim src/accessiweather/app.py  # Or your editor

# Run tests
pytest -v

# Then test in Windows without syncing!
```

**⚠️ Warning:** File I/O is slower on `/mnt/c/` from WSL. Better for small edits, not full development.

## BMAD System Considerations

### Files to Sync

**Always sync these:**
- `.bmad/` - The BMAD core and workflow system
- `docs/` - Your PRDs, workflow status, documentation
- `src/` - Your source code
- `pyproject.toml` - Project config
- `.gitignore` - Git exclusions

**Never sync these:**
- `.bmad-user-memory/` - Personal agent memory (user-specific)
- `.venv/`, `venv/` - Python virtual environments (rebuild per OS)
- `.briefcase/` - Briefcase build cache (rebuild per OS)
- `build/`, `dist/` - Build artifacts (rebuild per OS)
- `__pycache__/`, `*.pyc` - Python cache (auto-generated)

### BMAD Config Paths

BMAD uses `{project-root}` which resolves correctly on both platforms:
- **WSL:** `/home/josh/accessiweather`
- **Windows:** `C:\Users\YourName\accessiweather`

No changes needed! The config will work on both.

## Troubleshooting

### Issue: "WSL path not accessible from Windows"

**Solution:** Make sure WSL is running:
```powershell
wsl --status
wsl  # Start WSL if needed
```

### Issue: "Permission denied" on sync scripts

**Solution:**
```bash
# In WSL
chmod +x sync_to_windows.sh

# In Windows PowerShell (as Administrator)
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Issue: "Python not found" in Windows

**Solution:** Install Python on Windows separately from WSL:
1. Download from https://www.python.org/downloads/
2. Check "Add Python to PATH" during installation
3. Reinstall dependencies: `pip install -e .`

### Issue: ".bmad folder not syncing"

**Solution:** Ensure it's not in `.gitignore`:
```bash
# Check if .bmad is ignored
git check-ignore .bmad

# If it shows output, remove from .gitignore or use --force
git add -f .bmad/
```

### Issue: "Config files differ between WSL and Windows"

**Solution:** BMAD config uses user name from system:
- WSL: `/home/josh/.config/accessiweather/`
- Windows: `C:\Users\YourName\AppData\Local\accessiweather\`

These are SEPARATE configs. If you want shared settings:
1. Use portable mode (create `portable.txt` in project root)
2. Or sync `~/.config/accessiweather/` manually

## Sync Scripts Reference

### `sync_to_windows.sh` (Run in WSL)

Syncs from WSL development environment to Windows testing environment.

**Usage:**
```bash
cd ~/accessiweather
./sync_to_windows.sh
```

**What it syncs:**
- `.bmad/` → Complete BMAD system
- `src/` → Source code
- `docs/` → Documentation
- Config files → `pyproject.toml`, `.gitignore`, etc.

**What it excludes:**
- User-specific data (`.bmad-user-memory/`)
- Virtual environments
- Build artifacts
- Git repository (use git for that!)

### `sync_to_wsl.ps1` (Run in Windows PowerShell)

Syncs from Windows back to WSL (if you made changes in Windows).

**Usage:**
```powershell
cd C:\Users\YourName\accessiweather
.\sync_to_wsl.ps1
```

## Best Practices

### 1. **Single Source of Truth**

Choose one primary development location:
- **Recommended:** WSL (faster, better tooling)
- **Alternative:** Windows (if you prefer)

Only make significant changes in your primary location.

### 2. **Sync Before Testing**

Always sync before testing on the other platform:
```bash
# WSL → Windows
./sync_to_windows.sh && cd /mnt/c/Users/YourName/accessiweather && briefcase dev
```

### 3. **Use Git for Big Changes**

For major updates (new features, refactoring):
```bash
# WSL
git add .bmad/ docs/ src/
git commit -m "Add new feature"
git push

# Windows
git pull
```

### 4. **Separate Virtual Environments**

Never share virtual environments between WSL and Windows:
```bash
# WSL
cd ~/accessiweather
python3 -m venv .venv
source .venv/bin/activate

# Windows (separate venv!)
cd C:\Users\YourName\accessiweather
python -m venv .venv
.venv\Scripts\activate
```

### 5. **BMAD Workflows Work Everywhere**

Your BMAD workflows, PRDs, and documentation work identically:
```bash
# WSL
cd ~/accessiweather && copilot

# Windows
cd C:\Users\YourName\accessiweather && copilot
```

The analyst agent (Mary) will see the same workflow status, PRDs, and context!

## Quick Commands Cheat Sheet

### WSL → Windows Sync
```bash
cd ~/accessiweather && ./sync_to_windows.sh
```

### Windows → WSL Sync
```powershell
cd C:\Users\$env:USERNAME\accessiweather; .\sync_to_wsl.ps1
```

### Get Windows Path from WSL
```bash
wslpath -w ~/accessiweather
```

### Access WSL from Windows Explorer
```
Win+R → \\wsl.localhost\Ubuntu\home\josh\accessiweather
```

### Check BMAD Status (Works on Both)
```bash
# From project root
cat docs/bmm-workflow-status.yaml
```

---

## Summary

**For your use case (develop in WSL, test in Windows):**

1. ✅ Use `sync_to_windows.sh` for quick syncing
2. ✅ Keep `.bmad/` in git for easy sharing
3. ✅ Develop normally in WSL with full speed
4. ✅ Test in native Windows when needed
5. ✅ BMAD workflows work identically on both platforms

The BMAD system is fully cross-platform compatible! 🚀
