#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./setup_env.sh
#   ./setup_env.sh .venv
#   ./setup_env.sh .venv large-v3
#
# Creates a virtual environment, installs project dependencies,
# verifies ffmpeg is available, and optionally pre-downloads a Whisper model.

VENV_DIR="${1:-.venv}"
MODEL_TO_PRELOAD="${2:-}"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 is not installed or not on PATH." >&2
  exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "Error: ffmpeg was not found on PATH." >&2
  echo "Install ffmpeg first (required for media audio extraction)." >&2
  exit 1
fi

if ! command -v ffprobe >/dev/null 2>&1; then
  echo "Error: ffprobe was not found on PATH." >&2
  echo "Install ffmpeg/ffprobe first (required by media workflows)." >&2
  exit 1
fi

echo "ffmpeg detected: $(ffmpeg -version | head -n 1)"

echo "Creating virtual environment at: ${VENV_DIR}"
python3 -m venv "${VENV_DIR}"

# shellcheck source=/dev/null
source "${VENV_DIR}/bin/activate"

echo "Upgrading pip/setuptools/wheel..."
python -m pip install --upgrade pip setuptools wheel

echo "Installing project with optional OpenAI + dev dependencies..."
python -m pip install -e ".[openai,dev]"

if [[ -n "${MODEL_TO_PRELOAD}" ]]; then
  echo "Pre-downloading faster-whisper model: ${MODEL_TO_PRELOAD}"
  SRT_GEN_MODEL="${MODEL_TO_PRELOAD}" python -c "import os; from faster_whisper import WhisperModel; WhisperModel(os.environ['SRT_GEN_MODEL'], device='cpu', compute_type='int8')"
fi

echo
echo "Environment setup complete."
echo "Activate it with:"
echo "  source ${VENV_DIR}/bin/activate"
