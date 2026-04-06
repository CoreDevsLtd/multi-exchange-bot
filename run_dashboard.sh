#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

VENV_DIR=".venv"
PYTHON_BIN="$VENV_DIR/bin/python"
PIP_BIN="$VENV_DIR/bin/pip"
REQ_FILE="requirements.txt"
REQ_HASH_FILE="$VENV_DIR/.requirements.sha256"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 is not installed or not in PATH."
  exit 1
fi

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Creating virtual environment in $VENV_DIR ..."
  if ! python3 -m venv "$VENV_DIR"; then
    echo ""
    echo "Failed to create virtual environment."
    echo "On Debian/Ubuntu, install venv support with:"
    echo "  sudo apt update && sudo apt install -y python3-venv"
    echo "or (for version-specific package):"
    echo "  sudo apt install -y python3.12-venv"
    exit 1
  fi
fi

CURRENT_HASH="$(sha256sum "$REQ_FILE" | awk '{print $1}')"
SAVED_HASH=""

if [[ -f "$REQ_HASH_FILE" ]]; then
  SAVED_HASH="$(cat "$REQ_HASH_FILE")"
fi

if [[ "$CURRENT_HASH" != "$SAVED_HASH" ]]; then
  echo "Installing/updating dependencies ..."
  "$PYTHON_BIN" -m pip install --upgrade pip
  "$PIP_BIN" install -r "$REQ_FILE"
  echo "$CURRENT_HASH" > "$REQ_HASH_FILE"
else
  echo "Dependencies are up to date."
fi

echo "Starting dashboard on http://localhost:5000"
exec "$PYTHON_BIN" main_with_dashboard.py
