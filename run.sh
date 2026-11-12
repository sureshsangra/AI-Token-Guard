#!/bin/bash
# Convenient runner for Token Guard Proxy
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="${SCRIPT_DIR}/../venv/bin/python"

if [ -f "$VENV_PYTHON" ]; then
    PYTHON_CMD="$VENV_PYTHON"
else
    PYTHON_CMD="python3"
fi

exec "$PYTHON_CMD" "${SCRIPT_DIR}/server.py" "$@"
