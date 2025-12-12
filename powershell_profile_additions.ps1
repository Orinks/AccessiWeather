# PowerShell Profile Additions for Faster Command Execution
# Add these lines to your PowerShell profile to prevent hanging on git and other commands

# Disable git pager globally to prevent hanging
$env:GIT_PAGER = ""

# Alternative: Set git pager to cat (immediate output)
# $env:GIT_PAGER = "cat"

# Disable less pager
$env:PAGER = ""

# Set git config to never use pager
git config --global core.pager ""
git config --global pager.branch false
git config --global pager.diff false
git config --global pager.log false
git config --global pager.show false
git config --global pager.status false

# Disable colored output that can cause encoding issues
$env:FORCE_COLOR = "0"
$env:NO_COLOR = "1"

# Speed up PowerShell startup
$PSDefaultParameterValues['*:Encoding'] = 'utf8'

# Disable progress bars for faster downloads
$ProgressPreference = 'SilentlyContinue'

# Set git to use simple push/pull behavior
git config --global push.default simple
git config --global pull.rebase false
