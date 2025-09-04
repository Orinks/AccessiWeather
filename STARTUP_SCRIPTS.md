# AccessiWeather Startup Scripts

This directory contains three startup scripts to run the AccessiWeather application in development mode using Briefcase:

## Available Scripts

### 1. `start.ps1` (PowerShell) - **Recommended for Windows**
- **Usage**: `.\start.ps1`
- **Requirements**: PowerShell (available on all modern Windows systems)
- **Features**:
  - Colored output for better readability
  - Robust error handling with detailed error messages
  - Automatic fallback from uv to pip if needed
  - Works natively with Windows paths and virtual environments

### 2. `start.bat` (Batch File) - **Windows Command Prompt**
- **Usage**: `.\start.bat` or `start.bat`
- **Requirements**: Windows Command Prompt (cmd.exe)
- **Features**:
  - Compatible with older Windows systems
  - Simple and straightforward execution
  - No external dependencies

### 3. `start.sh` (Bash) - **Cross-platform**
- **Usage**: `bash start.sh`
- **Requirements**: Bash shell (Git Bash, WSL, Linux, macOS)
- **Features**:
  - Cross-platform compatibility
  - Unix-style environment detection
  - Works on Linux, macOS, and Windows with Git Bash

## Prerequisites

Before running any startup script, ensure you have:

1. **Virtual Environment**: A `.venv` directory in the project root
   ```bash
   uv venv
   ```

2. **Dependencies Installed**: All project dependencies installed in the virtual environment
   ```bash
   uv pip install -e .
   ```

3. **Briefcase**: Will be automatically installed if not present

## What the Scripts Do

1. **Validate Environment**: Check for virtual environment and project structure
2. **Activate Virtual Environment**: Activate the `.venv` virtual environment
3. **Install Briefcase**: Install briefcase if not already present
4. **Start Development Mode**: Run `briefcase dev` to start the application

## Troubleshooting

### Virtual Environment Not Found
If you see "Virtual environment not found", create one:
```bash
uv venv
uv pip install -e .
```

### Briefcase Installation Fails
If briefcase installation fails, try manually:
```bash
# Activate virtual environment first
# Windows PowerShell/CMD:
.venv\Scripts\activate

# Bash/Unix:
source .venv/bin/activate

# Then install briefcase
pip install briefcase
```

### Path Issues on Windows with Git Bash
If using Git Bash on Windows and encountering path issues, try the PowerShell script instead:
```powershell
.\start.ps1
```

## Development Mode

The scripts start AccessiWeather in development mode using `briefcase dev`, which:
- Runs the application directly from source code
- Enables hot reloading for faster development
- Shows debug output and logging information
- Does not require building/packaging the application

## Stopping the Application

Press `Ctrl+C` in the terminal to stop the application.
