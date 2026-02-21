#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./setup_env.sh
#   ./setup_env.sh .venv
#   ./setup_env.sh .venv large-v3 local
#   ./setup_env.sh .venv mlx-community/whisper-large-v3-mlx mlx
# Optional:
#   SRT_GEN_INSTALL_PROFILE=cpu|mlx|torch ./setup_env.sh .venv
#   SRT_GEN_INSTALL_TORCH_BACKEND=1 ./setup_env.sh .venv
#
# Creates a virtual environment, installs project dependencies,
# verifies ffmpeg is available, and optionally pre-downloads a Whisper model.

VENV_DIR="${1:-.venv}"
MODEL_TO_PRELOAD="${2:-}"
PRELOAD_BACKEND="${3:-auto}"
SKIP_MODEL_PRELOAD="${SRT_GEN_SKIP_MODEL_PRELOAD:-0}"
INSTALL_TORCH_BACKEND="${SRT_GEN_INSTALL_TORCH_BACKEND:-0}"
INSTALL_PROFILE="${SRT_GEN_INSTALL_PROFILE:-auto}"

OS_NAME="$(uname -s 2>/dev/null || true)"
ARCH_NAME="$(uname -m 2>/dev/null || true)"
IS_APPLE_SILICON=0
if [[ "${OS_NAME}" == "Darwin" && "${ARCH_NAME}" == "arm64" ]]; then
  IS_APPLE_SILICON=1
fi

resolve_install_profile() {
  local profile="${INSTALL_PROFILE}"
  local default_profile="cpu"
  if [[ "${IS_APPLE_SILICON}" -eq 1 ]]; then
    default_profile="mlx"
  fi

  # Backward compatibility for existing callers.
  if [[ "${profile}" == "auto" && "${INSTALL_TORCH_BACKEND}" == "1" ]]; then
    profile="torch"
  fi

  if [[ "${profile}" == "auto" && -t 0 && -t 1 ]]; then
    echo
    echo "Select backend components to install:"
    echo "  1) cpu   - faster-whisper (cross-platform)"
    if [[ "${IS_APPLE_SILICON}" -eq 1 ]]; then
      echo "  2) mlx   - mlx-whisper (Apple Silicon only)"
    fi
    echo "  3) torch - openai-whisper + torch (mps/cuda/cpu)"
    read -r -p "Choice [${default_profile}]: " profile
    profile="${profile:-${default_profile}}"
    case "${profile}" in
      1) profile="cpu" ;;
      2) profile="mlx" ;;
      3) profile="torch" ;;
    esac
  fi

  if [[ "${profile}" == "auto" ]]; then
    profile="${default_profile}"
  fi

  case "${profile}" in
    cpu|mlx|torch) ;;
    *)
      echo "Error: invalid install profile '${profile}'. Use cpu, mlx, or torch." >&2
      exit 1
      ;;
  esac

  if [[ "${profile}" == "mlx" && "${IS_APPLE_SILICON}" -ne 1 ]]; then
    echo "Error: install profile 'mlx' is only supported on Apple Silicon (Darwin arm64)." >&2
    exit 1
  fi

  echo "${profile}"
}

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

INSTALL_PROFILE_RESOLVED="$(resolve_install_profile)"
echo "Install profile: ${INSTALL_PROFILE_RESOLVED}"

EXTRAS="openai,dev"
if [[ "${INSTALL_PROFILE_RESOLVED}" == "mlx" ]]; then
  EXTRAS="${EXTRAS},apple"
fi
if [[ "${INSTALL_PROFILE_RESOLVED}" == "torch" ]]; then
  EXTRAS="${EXTRAS},torch"
fi

echo "Installing project extras: [${EXTRAS}]..."
python -m pip install -e ".[${EXTRAS}]"
if [[ "${INSTALL_PROFILE_RESOLVED}" != "torch" ]]; then
  echo "Tip: set SRT_GEN_INSTALL_PROFILE=torch (or SRT_GEN_INSTALL_TORCH_BACKEND=1) to install --backend torch dependencies."
fi

python_has_module() {
  local module="$1"
  python -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('${module}') else 1)"
}

TORCH_INSTALLED=0
WHISPER_INSTALLED=0
if python_has_module torch; then
  TORCH_INSTALLED=1
fi
if python_has_module whisper; then
  WHISPER_INSTALLED=1
fi

if [[ "${INSTALL_PROFILE_RESOLVED}" == "torch" ]]; then
  if [[ "${TORCH_INSTALLED}" -ne 1 || "${WHISPER_INSTALLED}" -ne 1 ]]; then
    echo "Error: torch backend dependencies are incomplete." >&2
    echo "Expected both 'torch' and 'openai-whisper' after install." >&2
    echo "Try: python -m pip install -e '.[torch]'" >&2
    exit 1
  fi
  echo "Torch backend dependencies verified (torch + openai-whisper)."
elif [[ "${TORCH_INSTALLED}" -eq 1 && "${WHISPER_INSTALLED}" -ne 1 ]]; then
  echo "Detected 'torch' without 'openai-whisper'. Installing missing dependency for --backend torch..."
  if python -m pip install openai-whisper; then
    if python_has_module whisper; then
      echo "Installed 'openai-whisper' successfully."
    else
      echo "Warning: 'openai-whisper' install completed but import check failed." >&2
      echo "Run: python -m pip install -e '.[torch]'" >&2
    fi
  else
    echo "Warning: could not install 'openai-whisper' automatically." >&2
    echo "Run: python -m pip install -e '.[torch]'" >&2
  fi
fi

if [[ "${PRELOAD_BACKEND}" != "auto" && "${PRELOAD_BACKEND}" != "local" && "${PRELOAD_BACKEND}" != "mlx" ]]; then
  echo "Error: invalid preload backend '${PRELOAD_BACKEND}'. Use auto, local, or mlx." >&2
  exit 1
fi

DEFAULT_PRELOAD_BACKEND="local"
if [[ "${INSTALL_PROFILE_RESOLVED}" == "mlx" ]]; then
  DEFAULT_PRELOAD_BACKEND="mlx"
fi

if [[ -z "${MODEL_TO_PRELOAD}" && "${DEFAULT_PRELOAD_BACKEND}" == "mlx" ]]; then
  MODEL_TO_PRELOAD="mlx-community/whisper-large-v3-mlx"
fi

if [[ "${SKIP_MODEL_PRELOAD}" == "1" ]]; then
  echo "Skipping model pre-download because SRT_GEN_SKIP_MODEL_PRELOAD=1."
elif [[ -n "${MODEL_TO_PRELOAD}" ]]; then
  SELECTED_PRELOAD_BACKEND="${PRELOAD_BACKEND}"
  if [[ "${SELECTED_PRELOAD_BACKEND}" == "auto" ]]; then
    SELECTED_PRELOAD_BACKEND="${DEFAULT_PRELOAD_BACKEND}"
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
