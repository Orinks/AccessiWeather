#!/usr/bin/env bash

set -euo pipefail

UV_BIN=""
if command -v uv >/dev/null 2>&1; then
    UV_BIN=$(command -v uv)
elif [ -x "${HOME:-}/.local/bin/uv" ]; then
    UV_BIN="${HOME:-}/.local/bin/uv"
fi

if [ -n "$UV_BIN" ]; then
    if [ -d ".venv/Scripts" ] && [ ! -x ".venv/bin/python" ]; then
        export UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-.venv-wsl}"
    fi
    exec "$UV_BIN" run --extra dev pytest tests/ -m "not integration and not live_only" --maxfail=5 -x
fi

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

exec "$PYTHON_BIN" -m pytest tests/ -m "not integration and not live_only" --maxfail=5 -x
