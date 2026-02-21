#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./setup_env.sh
#   ./setup_env.sh .venv
#   ./setup_env.sh .venv large-v3 local
#   ./setup_env.sh .venv mlx-community/whisper-large-v3-mlx mlx
#
# Creates a virtual environment, installs project dependencies,
# verifies ffmpeg is available, and optionally pre-downloads a Whisper model.

VENV_DIR="${1:-.venv}"
MODEL_TO_PRELOAD="${2:-}"
PRELOAD_BACKEND="${3:-auto}"
SKIP_MODEL_PRELOAD="${SRT_GEN_SKIP_MODEL_PRELOAD:-0}"

OS_NAME="$(uname -s 2>/dev/null || true)"
ARCH_NAME="$(uname -m 2>/dev/null || true)"
IS_APPLE_SILICON=0
if [[ "${OS_NAME}" == "Darwin" && "${ARCH_NAME}" == "arm64" ]]; then
  IS_APPLE_SILICON=1
fi

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
echo "Platform detected: ${OS_NAME} ${ARCH_NAME}"

echo "Creating virtual environment at: ${VENV_DIR}"
python3 -m venv "${VENV_DIR}"

# shellcheck source=/dev/null
source "${VENV_DIR}/bin/activate"

echo "Upgrading pip/setuptools/wheel..."
python -m pip install --upgrade pip setuptools wheel

if [[ "${IS_APPLE_SILICON}" -eq 1 ]]; then
  echo "Apple Silicon detected: installing Apple MLX dependencies too..."
  python -m pip install -e ".[openai,dev,apple]"
else
  echo "Installing project with optional OpenAI + dev dependencies..."
  python -m pip install -e ".[openai,dev]"
fi

if [[ "${PRELOAD_BACKEND}" != "auto" && "${PRELOAD_BACKEND}" != "local" && "${PRELOAD_BACKEND}" != "mlx" ]]; then
  echo "Error: invalid preload backend '${PRELOAD_BACKEND}'. Use auto, local, or mlx." >&2
  exit 1
fi

if [[ -z "${MODEL_TO_PRELOAD}" && "${IS_APPLE_SILICON}" -eq 1 ]]; then
  MODEL_TO_PRELOAD="mlx-community/whisper-large-v3-mlx"
fi

if [[ "${SKIP_MODEL_PRELOAD}" == "1" ]]; then
  echo "Skipping model pre-download because SRT_GEN_SKIP_MODEL_PRELOAD=1."
elif [[ -n "${MODEL_TO_PRELOAD}" ]]; then
  SELECTED_PRELOAD_BACKEND="${PRELOAD_BACKEND}"
  if [[ "${SELECTED_PRELOAD_BACKEND}" == "auto" ]]; then
    if [[ "${IS_APPLE_SILICON}" -eq 1 ]]; then
      SELECTED_PRELOAD_BACKEND="mlx"
    else
      SELECTED_PRELOAD_BACKEND="local"
    fi
  fi

  if [[ "${SELECTED_PRELOAD_BACKEND}" == "mlx" && "${IS_APPLE_SILICON}" -ne 1 ]]; then
    echo "Error: mlx model preload is only supported on Apple Silicon (Darwin arm64)." >&2
    exit 1
  fi

  if [[ "${SELECTED_PRELOAD_BACKEND}" == "local" ]]; then
    echo "Pre-downloading faster-whisper model: ${MODEL_TO_PRELOAD}"
    if ! SRT_GEN_MODEL="${MODEL_TO_PRELOAD}" python -c "import os; from faster_whisper import WhisperModel; WhisperModel(os.environ['SRT_GEN_MODEL'], device='cpu', compute_type='int8')"; then
      echo "Warning: faster-whisper model pre-download failed. Continuing setup." >&2
      echo "You can still run srt-gen and let model download on first use." >&2
    fi
  else
    echo "Pre-downloading mlx-whisper model: ${MODEL_TO_PRELOAD}"
    if ! SRT_GEN_MODEL="${MODEL_TO_PRELOAD}" python - <<'PY'
import os
import tempfile
import wave

import mlx_whisper

model = os.environ["SRT_GEN_MODEL"]
path = ""
try:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        path = tmp.name
    with wave.open(path, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\x00\x00" * 1600)
    mlx_whisper.transcribe(path, path_or_hf_repo=model, task="translate", verbose=False)
finally:
    if path and os.path.exists(path):
        os.remove(path)
PY
    then
      echo "Warning: mlx-whisper model pre-download failed. Continuing setup." >&2
      echo "You can still run srt-gen and let model download on first use." >&2
    fi
  fi
fi

echo
echo "Environment setup complete."
echo "Activate it with:"
echo "  source ${VENV_DIR}/bin/activate"
