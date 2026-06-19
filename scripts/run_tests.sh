#!/usr/bin/env bash
set -euo pipefail

SKIP_COMPILE=0
if [[ "${1:-}" == "--skip-compile" ]]; then
  SKIP_COMPILE=1
fi

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

if [[ -x "$PROJECT_ROOT/.venv/bin/python" ]]; then
  PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"
elif [[ -x "$PROJECT_ROOT/.venv/Scripts/python.exe" ]]; then
  PYTHON_BIN="$PROJECT_ROOT/.venv/Scripts/python.exe"
elif [[ -n "${PYTHON_BIN:-}" ]]; then
  PYTHON_BIN="$PYTHON_BIN"
elif command -v python3.12 >/dev/null 2>&1; then
  PYTHON_BIN="python3.12"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  echo "No Python interpreter found. Run scripts/setup_unix.sh first or install Python 3.12." >&2
  exit 1
fi

PYTHON_VERSION="$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [[ "$PYTHON_VERSION" != "3.12" ]]; then
  echo "This project requires Python 3.12. Current interpreter is $PYTHON_VERSION at $PYTHON_BIN" >&2
  exit 1
fi

echo "Using Python interpreter: $PYTHON_BIN"
if [[ "$SKIP_COMPILE" != "1" ]]; then
  "$PYTHON_BIN" -m compileall mk8dx_video_result_extractor
fi
"$PYTHON_BIN" -m unittest discover
