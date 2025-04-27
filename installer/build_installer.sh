#!/bin/bash
# AccessiWeather Installer Build Script
# This bash script builds the AccessiWeather application and creates an installer for Unix-like systems

# Exit on error
set -e

# Enable color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Determine script location and project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Change to project root directory if we're in the installer directory
CURRENT_DIR="$(pwd)"
if [ "$CURRENT_DIR" = "$SCRIPT_DIR" ]; then
    echo -e "${YELLOW}Running from installer directory. Changing to project root...${NC}"
    cd "$PROJECT_ROOT"
    echo -e "${GREEN}Working directory set to: $PROJECT_ROOT${NC}"
fi

# Function to extract version from setup.py
get_app_version() {
    local setup_path="$PROJECT_ROOT/setup.py"
    if [ -f "$setup_path" ]; then
        local version_line=$(grep -E 'version\s*=\s*"([0-9\.]+)"' "$setup_path")
        if [[ $version_line =~ version[[:space:]]*=[[:space:]]*\"([0-9\.]+)\" ]]; then
            echo "${BASH_REMATCH[1]}"
            return 0
        fi
    fi
    echo -e "${YELLOW}Warning: Could not extract version from setup.py. Using default version.${NC}"
    echo "0.0.0"
}

# Set environment variables
APP_NAME="AccessiWeather"
APP_VERSION=$(get_app_version)
PYINSTALLER_OPTS="--clean --noconfirm --onedir --windowed --name $APP_NAME"

echo -e "${CYAN}Building $APP_NAME version $APP_VERSION${NC}"

# Function to check for running processes that might interfere with the build
check_running_processes() {
    echo -e "\n${YELLOW}===== Checking for processes that might interfere with the build =====${NC}"

    # Check if the application is running
    local app_processes=$(pgrep -f "$APP_NAME" 2>/dev/null || true)

    # Check for Python processes that might be related to our app
    local python_processes=$(pgrep -f "python.*$APP_NAME\|python.*accessiweather" 2>/dev/null || true)

    # Combine all detected processes
    local all_processes="$app_processes $python_processes"
    all_processes=$(echo "$all_processes" | tr ' ' '\n' | sort -u | tr '\n' ' ')

    if [ -n "$all_processes" ]; then
        echo -e "${RED}The following processes might interfere with the build process:${NC}"
        for pid in $all_processes; do
            local process_name=$(ps -p "$pid" -o comm= 2>/dev/null || echo "Unknown")
            echo -e "${RED}  - $process_name (PID: $pid)${NC}"
        done

        # Automatically close interfering processes without asking
        echo -e "${YELLOW}Automatically closing interfering processes...${NC}"
        for pid in $all_processes; do
            local process_name=$(ps -p "$pid" -o comm= 2>/dev/null || echo "Unknown")
            if kill -15 "$pid" 2>/dev/null; then
                echo -e "${GREEN}Closed process: $process_name (PID: $pid)${NC}"
            else
                echo -e "${RED}Failed to close process: $process_name (PID: $pid)${NC}"
            fi
        done

        # Give processes time to fully close
        sleep 2

        # Check if any processes are still running
        local remaining_processes=""
        for pid in $all_processes; do
            if ps -p "$pid" >/dev/null 2>&1; then
                local process_name=$(ps -p "$pid" -o comm= 2>/dev/null || echo "Unknown")
                remaining_processes="$remaining_processes $pid"
                echo -e "${RED}  - $process_name (PID: $pid)${NC}"
            fi
        done

        if [ -n "$remaining_processes" ]; then
            echo -e "${RED}Some processes could not be closed:${NC}"
            echo -e "${YELLOW}Continuing anyway...${NC}"
        fi
    else
        echo -e "${GREEN}No interfering processes detected.${NC}"
    fi
}

# Function to clean build directories
clean_build_directories() {
    echo -e "\n${YELLOW}===== Cleaning build directories =====${NC}"

    # Automatically clean the directories without asking
    echo -e "${YELLOW}Automatically cleaning build and dist directories...${NC}"

    # Clean dist directory
    if [ -d "dist" ]; then
        echo -e "${YELLOW}Cleaning dist directory...${NC}"
        if rm -rf "dist"; then
            echo -e "${GREEN}dist directory cleaned successfully.${NC}"
        else
            echo -e "${RED}Error cleaning dist directory.${NC}"
            echo -e "${RED}Some files may be locked by other processes.${NC}"
        fi
    fi

    # Clean build directory
    if [ -d "build" ]; then
        echo -e "${YELLOW}Cleaning build directory...${NC}"
        if rm -rf "build"; then
            echo -e "${GREEN}build directory cleaned successfully.${NC}"
        else
            echo -e "${RED}Error cleaning build directory.${NC}"
            echo -e "${RED}Some files may be locked by other processes.${NC}"
        fi
    fi

    # Clean spec file
    if [ -f "$APP_NAME.spec" ]; then
        echo -e "${YELLOW}Removing spec file...${NC}"
        if rm -f "$APP_NAME.spec"; then
            echo -e "${GREEN}Spec file removed successfully.${NC}"
        else
            echo -e "${RED}Error removing spec file.${NC}"
        fi
    fi
}

# Function to detect the operating system
detect_os() {
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
        echo "windows"
    else
        echo "unix"
    fi
}

# Function to compare version strings
compare_version() {
    if [[ "$1" == "$2" ]]; then
        echo 0
        return
    fi

    local IFS=.
    local i ver1=($1) ver2=($2)

    # Fill empty fields with zeros
    for ((i=${#ver1[@]}; i<${#ver2[@]}; i++)); do
        ver1[i]=0
    done
    for ((i=${#ver2[@]}; i<${#ver1[@]}; i++)); do
        ver2[i]=0
    done

    # Compare version numbers
    for ((i=0; i<${#ver1[@]}; i++)); do
        if [[ ${ver1[i]} -gt ${ver2[i]} ]]; then
            echo 1
            return
        fi
        if [[ ${ver1[i]} -lt ${ver2[i]} ]]; then
            echo -1
            return
        fi
    done

    echo 0
}

# Function to check if Python is installed with the minimum required version
check_python_installed() {
    local min_version=${1:-"3.6.0"}

    if command -v python3 &>/dev/null; then
        local python_cmd="python3"
    elif command -v python &>/dev/null; then
        local python_cmd="python"
    else
        echo -e "${RED}Python is not installed or not in PATH${NC}"
        return 1
    fi

    local python_version=$($python_cmd --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')

    if [ -n "$python_version" ]; then
        local version_comparison=$(compare_version "$python_version" "$min_version")

        if [ "$version_comparison" -ge 0 ]; then
            echo -e "${GREEN}Python $python_version is installed (minimum required: $min_version)${NC}"
            return 0
        else
            echo -e "${YELLOW}Python $python_version is installed but version $min_version or higher is required${NC}"
            return 1
        fi
    else
        echo -e "${RED}Failed to determine Python version${NC}"
        return 1
    fi
}

# Function to get the list of required dependencies
get_required_dependencies() {
    # Define the list of required dependencies based on setup.py
    local dependencies=(
        "wxPython"
        "requests"
        "plyer"
        "geopy"
        "python-dateutil"
        "beautifulsoup4"
        "PyInstaller"
    )

    echo "${dependencies[@]}"
}

# Function to check if a specific package is installed
check_dependency_installed() {
    local package_name="$1"

    if command -v python3 &>/dev/null; then
        local python_cmd="python3"
    else
        local python_cmd="python"
    fi

    # Special case for PyInstaller - check if the module can be imported
    if [ "$package_name" = "PyInstaller" ]; then
        if $python_cmd -c "import PyInstaller" &>/dev/null; then
            # Try to get the version if possible
            local package_version=$($python_cmd -c "import PyInstaller; print(PyInstaller.__version__)" 2>/dev/null || echo "installed")
            echo -e "${GREEN}$package_name $package_version is installed${NC}"
            return 0
        else
            echo -e "${YELLOW}$package_name is not installed${NC}"
            return 1
        fi
    fi

    # Standard check for other packages using pip list
    if $python_cmd -m pip list | grep -E "^$package_name[[:space:]]+" &>/dev/null; then
        local package_version=$($python_cmd -m pip list | grep -E "^$package_name[[:space:]]+" | awk '{print $2}')
        echo -e "${GREEN}$package_name $package_version is installed${NC}"
        return 0
    else
        echo -e "${YELLOW}$package_name is not installed${NC}"
        return 1
    fi
}

# Function to install a specific package
install_dependency() {
    local package_name="$1"
    local upgrade="$2"

    if command -v python3 &>/dev/null; then
        local python_cmd="python3"
    else
        local python_cmd="python"
    fi

    local upgrade_flag=""
    if [ "$upgrade" = "true" ]; then
        upgrade_flag="--upgrade"
    fi

    echo -e "${CYAN}Installing $package_name...${NC}"

    # Special handling for wxPython which might need specific installation parameters
    if [ "$package_name" = "wxPython" ]; then
        $python_cmd -m pip install $upgrade_flag --no-cache-dir $package_name
    else
        $python_cmd -m pip install $upgrade_flag $package_name
    fi

    if check_dependency_installed "$package_name"; then
        echo -e "${GREEN}$package_name installed successfully${NC}"
        return 0
    else
        echo -e "${RED}Failed to install $package_name${NC}"
        return 1
    fi
}

# Function to check and install all required dependencies
check_install_dependencies() {
    local force="$1"
    local all_dependencies_installed=true
    local dependencies=($(get_required_dependencies))

    for dependency in "${dependencies[@]}"; do
        if ! check_dependency_installed "$dependency" || [ "$force" = "true" ]; then
            if ! install_dependency "$dependency" "$force"; then
                all_dependencies_installed=false
            fi
        fi
    done

    if [ "$all_dependencies_installed" = true ]; then
        return 0
    else
        return 1
    fi
}

# Create build directories if they don't exist
mkdir -p "dist" "build"

# Check for running processes
check_running_processes

# Clean build directories
clean_build_directories

# Step 1: Check and install dependencies
echo -e "\n${CYAN}===== Step 1: Checking and installing dependencies =====${NC}"

# Check if Python is installed
if ! check_python_installed; then
    echo -e "${RED}Please install Python 3.6 or higher and add it to your PATH${NC}"
    exit 1
fi

# Check and install dependencies
echo -e "${CYAN}Checking and installing dependencies...${NC}"
if ! check_install_dependencies "false"; then
    echo -e "${RED}Failed to install all required dependencies. Please check the error messages above.${NC}"

    # Automatically retry with force option
    echo -e "${YELLOW}Retrying with force option to reinstall all dependencies...${NC}"
    if ! check_install_dependencies "true"; then
        echo -e "${RED}Failed to install all required dependencies even with the force option. Please install them manually.${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}All dependencies are installed successfully.${NC}"

# Step 2: Build executable with PyInstaller
echo -e "\n${CYAN}===== Step 2: Building executable with PyInstaller =====${NC}"

if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
else
    PYTHON_CMD="python"
fi

$PYTHON_CMD -m PyInstaller $PYINSTALLER_OPTS \
    --hidden-import=plyer.platforms.linux.notification \
    --hidden-import=plyer.platforms.macosx.notification \
    --hidden-import=dateutil.parser \
    "src/accessiweather/main.py"

# Step 3: Create portable ZIP archive
echo -e "\n${CYAN}===== Step 3: Creating portable ZIP archive =====${NC}"
os_type=$(detect_os)
if [ "$os_type" = "windows" ]; then
    # Use PowerShell's Compress-Archive on Windows
    echo -e "${YELLOW}Detected Windows environment, using PowerShell's Compress-Archive...${NC}"
    powershell -Command "Compress-Archive -Path \"dist/$APP_NAME/*\" -DestinationPath \"dist/${APP_NAME}_Portable_v${APP_VERSION}.zip\" -Force"
else
    # Use zip command on Unix-like systems
    echo -e "${YELLOW}Detected Unix-like environment, using zip command...${NC}"
    (cd "dist/$APP_NAME" && zip -r "../${APP_NAME}_Portable_v${APP_VERSION}.zip" .)
fi

# Final message
echo -e "\n${GREEN}===== Build Complete =====${NC}"
echo -e "${CYAN}Portable: dist/${APP_NAME}_Portable_v${APP_VERSION}.zip${NC}"

# Check for any processes that might have been started during the build
echo -e "\n${YELLOW}===== Checking for new processes =====${NC}"
new_processes=$(pgrep -f "$APP_NAME\|python.*$APP_NAME\|python.*accessiweather" 2>/dev/null || true)

if [ -n "$new_processes" ]; then
    echo -e "${YELLOW}The following processes were started during the build:${NC}"
    for pid in $new_processes; do
        process_name=$(ps -p "$pid" -o comm= 2>/dev/null || echo "Unknown")
        echo -e "${YELLOW}  - $process_name (PID: $pid)${NC}"
    done

    # Automatically close processes without asking
    echo -e "${YELLOW}Automatically closing processes started during the build...${NC}"
    for pid in $new_processes; do
        process_name=$(ps -p "$pid" -o comm= 2>/dev/null || echo "Unknown")
        if kill -15 "$pid" 2>/dev/null; then
            echo -e "${GREEN}Closed process: $process_name (PID: $pid)${NC}"
        else
            echo -e "${RED}Failed to close process: $process_name (PID: $pid)${NC}"
        fi
    done
else
    echo -e "${GREEN}No new processes were detected.${NC}"
fi

# Verify output files
echo -e "\n${YELLOW}===== Verifying output files =====${NC}"
portable_path="dist/${APP_NAME}_Portable_v${APP_VERSION}.zip"
executable_path="dist/$APP_NAME/$APP_NAME"

all_files_exist=true

if [ -f "$executable_path" ] || [ -f "${executable_path}.exe" ]; then
    echo -e "${GREEN}✓ Executable created successfully: $executable_path${NC}"
else
    echo -e "${RED}✗ Executable was not created: $executable_path${NC}"
    all_files_exist=false
fi

if [ -f "$portable_path" ]; then
    portable_size=$(du -h "$portable_path" | cut -f1)
    echo -e "${GREEN}✓ Portable ZIP created successfully: $portable_path (Size: $portable_size)${NC}"
else
    echo -e "${RED}✗ Portable ZIP was not created: $portable_path${NC}"
    all_files_exist=false
fi

if [ "$all_files_exist" = true ]; then
    echo -e "\n${GREEN}Build process completed successfully!${NC}"
else
    echo -e "\n${RED}Build process completed with errors. Some output files are missing.${NC}"
fi
