#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

PYTHON_BIN="${PYTHON_BIN:-python3.12}"
TORCH_MODE="${TORCH_MODE:-auto}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python executable not found: $PYTHON_BIN" >&2
  echo "Install Python 3.12 and rerun this script, or set PYTHON_BIN to your Python 3.12 executable." >&2
  exit 1
fi

PYTHON_VERSION="$($PYTHON_BIN -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [[ "$PYTHON_VERSION" != "3.12" ]]; then
  echo "This project requires Python 3.12. Current interpreter is $PYTHON_VERSION at $PYTHON_BIN" >&2
  echo "Set PYTHON_BIN to a Python 3.12 interpreter and rerun this script." >&2
  exit 1
fi

if [[ ! -x ".venv/bin/python" ]]; then
  "$PYTHON_BIN" -m venv .venv
fi

VENV_PYTHON=".venv/bin/python"
VENV_VERSION="$($VENV_PYTHON -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [[ "$VENV_VERSION" != "3.12" ]]; then
  echo "This project requires Python 3.12. Current .venv interpreter is $VENV_VERSION at $VENV_PYTHON" >&2
  echo "Delete .venv, set PYTHON_BIN to Python 3.12, and rerun this script." >&2
  exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "FFmpeg was not found on PATH. Install FFmpeg with your package manager and rerun setup." >&2
  exit 1
fi

echo "Using Python interpreter: $VENV_PYTHON"
TORCH_DECISION_JSON="$("$VENV_PYTHON" -m mk8dx_video_result_extractor.setup_torch --mode "$TORCH_MODE" --format json)"

print_decision_field() {
  "$VENV_PYTHON" -c 'import json, sys; print(json.loads(sys.argv[1]).get(sys.argv[2], ""))' "$TORCH_DECISION_JSON" "$1"
}

echo "Hardware scan:"
echo "  OS: $(print_decision_field system) ($(print_decision_field machine))"
"$VENV_PYTHON" -c 'import json, sys; data=json.loads(sys.argv[1]); names=data.get("gpu_names") or []; print("  GPUs: " + (", ".join(names) if names else "none reported"))' "$TORCH_DECISION_JSON"
echo "  nvidia-smi available: $(print_decision_field nvidia_smi_available)"
echo "  requested torch mode: $(print_decision_field requested_mode)"
echo "  selected torch mode: $(print_decision_field selected_mode)"
echo "  expected GPU OCR: $(print_decision_field expected_gpu_ocr)"
echo "  reason: $(print_decision_field reason)"
"$VENV_PYTHON" -c 'import json, sys; data=json.loads(sys.argv[1]); [print("  warning: " + item) for item in data.get("warnings", []) if item]' "$TORCH_DECISION_JSON"
"$VENV_PYTHON" -c 'import json, sys; note=json.loads(sys.argv[1]).get("post_install_note") or ""; print("  note: " + note) if note else None' "$TORCH_DECISION_JSON"

if [[ "$(print_decision_field requires_manual_setup)" == "True" || "$(print_decision_field requires_manual_setup)" == "true" ]]; then
  echo "$(print_decision_field reason)" >&2
  exit 1
fi

TORCH_PIP_ARGS=()
while IFS= read -r arg; do
  TORCH_PIP_ARGS+=("$arg")
done < <("$VENV_PYTHON" -c 'import json, sys; [print(arg) for arg in json.loads(sys.argv[1]).get("pip_args", [])]' "$TORCH_DECISION_JSON")
if [[ "${#TORCH_PIP_ARGS[@]}" -eq 0 ]]; then
  echo "PyTorch selection did not produce install arguments." >&2
  exit 1
fi

".venv/bin/python" -m pip install --upgrade pip
".venv/bin/python" -m pip install "${TORCH_PIP_ARGS[@]}"
".venv/bin/python" -m pip install -e ".[gui]"

if [[ ! -f "config/app_config.json" ]]; then
  if [[ ! -f "config/app_config.example.json" ]]; then
    echo "Missing config/app_config.example.json. Restore it from git before running setup." >&2
    exit 1
  fi
  cp "config/app_config.example.json" "config/app_config.json"
  echo "Created local config/app_config.json from config/app_config.example.json."
fi

".venv/bin/mk8-local-play" --check

echo
echo "Setup finished."
echo "This app runs from the local .venv in this project folder."
echo "No global Python package install or PATH change is required for mk8-local-play."
echo "PyTorch mode selected by setup: $(print_decision_field selected_mode). Use --check to confirm the active OCR backend."
echo "Next steps:"
echo "1. Put videos into Input_Videos."
echo "2. Run .venv/bin/mk8-local-play to open the GUI."
echo "3. Or run .venv/bin/mk8-local-play --all from the terminal."
echo "   or run .venv/bin/python -m mk8dx_video_result_extractor.main --all"
