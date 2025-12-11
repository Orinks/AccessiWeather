#!/bin/bash
# Validate BMAD system after syncing to Windows

echo "🔍 BMAD Cross-Platform Validation"
echo "=================================="
echo ""

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo "❌ Error: Not in project root (pyproject.toml not found)"
    exit 1
fi

echo "✅ In project root"

# Check for BMAD core files
echo ""
echo "Checking BMAD core files..."

required_files=(
    ".bmad/core/config.yaml"
    ".bmad/bmm/config.yaml"
    ".bmad/bmm/agents/analyst.md"
    ".bmad/bmm/workflows/workflow-status/workflow.yaml"
    "docs/bmm-workflow-status.yaml"
    "docs/ai-weather-explanations-prd.md"
)

missing_count=0
for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        echo "  ✅ $file"
    else
        echo "  ❌ MISSING: $file"
        ((missing_count++))
    fi
done

if [ $missing_count -gt 0 ]; then
    echo ""
    echo "⚠️  Warning: $missing_count required file(s) missing"
    echo "   Run sync script again or check .gitignore"
fi

# Check BMAD config
echo ""
echo "Checking BMAD configuration..."

if grep -q "user_name:" .bmad/core/config.yaml; then
    username=$(grep "user_name:" .bmad/core/config.yaml | cut -d: -f2 | xargs)
    echo "  ✅ User name: $username"
else
    echo "  ❌ User name not configured"
fi

if grep -q "output_folder:" .bmad/core/config.yaml; then
    output=$(grep "output_folder:" .bmad/core/config.yaml | cut -d: -f2- | xargs)
    echo "  ✅ Output folder: $output"
else
    echo "  ❌ Output folder not configured"
fi

# Check for excluded files (should NOT be synced)
echo ""
echo "Checking for files that should NOT be synced..."

should_not_exist=(
    ".bmad-user-memory/"
    ".venv/"
    "venv/"
    ".briefcase/"
    "build/"
)

for item in "${should_not_exist[@]}"; do
    if [ -e "$item" ]; then
        echo "  ⚠️  Found: $item (should be rebuilt on this platform)"
    else
        echo "  ✅ Not present: $item"
    fi
done

# Check platform
echo ""
echo "Platform information:"
if [ -f "/proc/version" ] && grep -qi microsoft /proc/version; then
    echo "  📍 Running in WSL"
elif [ "$(uname)" == "Linux" ]; then
    echo "  📍 Running in Linux"
elif [ "$(uname)" == "Darwin" ]; then
    echo "  📍 Running in macOS"
else
    echo "  📍 Running in unknown environment"
fi

# Check Python
echo ""
echo "Python environment:"
if command -v python3 &> /dev/null; then
    python_version=$(python3 --version)
    echo "  ✅ $python_version"
else
    echo "  ❌ Python 3 not found"
fi

# Summary
echo ""
echo "=================================="
if [ $missing_count -eq 0 ]; then
    echo "✅ BMAD system validated successfully!"
    echo ""
    echo "You can now:"
    echo "  • Run workflows: copilot"
    echo "  • Check status: cat docs/bmm-workflow-status.yaml"
    echo "  • View PRD: cat docs/ai-weather-explanations-prd.md"
else
    echo "⚠️  Some issues detected. Check output above."
    echo ""
    echo "To fix:"
    echo "  • Re-run sync script"
    echo "  • Check .gitignore excludes"
    echo "  • Verify source has all files"
fi
echo "=================================="
