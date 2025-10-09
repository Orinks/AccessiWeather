#!/usr/bin/env bash

set -euo pipefail

choose_python() {
    for candidate in \
        "${VIRTUAL_ENV:-}"/bin/python \
        "./.venv-wsl/bin/python" \
        "./.venv/bin/python" \
        "python3" \
        "python"; do
        if [ -n "$candidate" ] && command -v "$candidate" >/dev/null 2>&1; then
            echo "$candidate"
            return 0
        fi
    done

    echo "Unable to locate a Python interpreter for pytest" >&2
    return 1
}

PYTHON_BIN=$(choose_python)

exec "$PYTHON_BIN" -m pytest tests/ -m "unit" --maxfail=5 -x
