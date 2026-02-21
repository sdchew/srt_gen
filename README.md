# srt_gen

`srt_gen` is a cross-platform Python CLI that generates English `.srt` subtitle files from video or audio input.

It is built for local-first usage with Whisper and supports four local/cloud backend paths:
- `mlx-whisper` (preferred on Apple Silicon)
- `faster-whisper` (cross-platform local backend)
- OpenAI Whisper (PyTorch backend; supports `mps`, `cuda`, `cpu`)
- OpenAI audio translation API (optional cloud backend)

## What It Does
- Accepts media input (any format ffmpeg can decode).
- Extracts mono 16k audio from the source.
- Transcribes and translates speech to English.
- Splits text into readable subtitle cues.
- Writes a standards-compliant `.srt` file.

## Current v1 Scope
- Source language: any language (`--source-lang auto` by default).
- Output language: always English.
- Backends:
  - `auto` (default): picks `mlx` on Apple Silicon, otherwise `local`
  - `mlx`: `mlx-whisper` backend (Apple Silicon only)
  - `local`: `faster-whisper`
  - `torch`: OpenAI Whisper via PyTorch (`mps`/`cuda`/`cpu`)
  - `openai` (optional): OpenAI audio translation API

## Requirements
- Python `3.10+`
- `ffmpeg` and `ffprobe` on `PATH`

## Quick Start

### 1. Setup environment and dependencies
```bash
./setup_env.sh .venv
```

What this does:
- verifies `python3`, `ffmpeg`, and `ffprobe`
- creates `.venv`
- installs project dependencies (`.[openai,dev]`), plus Apple extras on Apple Silicon
- prompts for install profile in interactive shells: `cpu`, `mlx`, or `torch`
- verifies backend dependency consistency and auto-fixes common `torch`/`openai-whisper` mismatch
- pre-downloads a default model on Apple Silicon (`mlx-community/whisper-large-v3-mlx`)

Optional: preselect profile without prompt (useful for CI):
```bash
SRT_GEN_INSTALL_PROFILE=torch ./setup_env.sh .venv
```

Optional custom pre-download:
```bash
# faster-whisper model
./setup_env.sh .venv large-v3 local

# mlx-whisper model
./setup_env.sh .venv mlx-community/whisper-large-v3-mlx mlx
```

### 2. Activate virtual environment
macOS/Linux:
```bash
source .venv/bin/activate
```

Windows PowerShell:
```powershell
.venv\Scripts\Activate.ps1
```

### 3. Run subtitle generation
```bash
srt-gen /path/to/video.mp4
```

If `-o/--output` is omitted, output defaults to the same base filename with `.srt`:
- input: `meeting.mp4`
- output: `meeting.srt`

## Installation (Manual Alternative)
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install --upgrade pip setuptools wheel
pip install -e .
```

Optional OpenAI API support:
```bash
pip install -e ".[openai]"
```

Apple Silicon optional extras:
```bash
pip install -e ".[apple]"
```

Optional PyTorch Whisper backend (`--backend torch`):
```bash
pip install -e ".[torch]"
```

## Usage Examples

### Basic (auto backend)
```bash
srt-gen input.mp4
```

### Custom output path
```bash
srt-gen input.mp4 -o subtitles/output.srt
```

### Use a faster/lighter local model
```bash
srt-gen input.mp4 --backend local --model medium
```

### Use MLX backend explicitly (Apple Silicon)
```bash
srt-gen input.mp4 --backend mlx --model mlx-community/whisper-large-v3-mlx
```

### Use PyTorch Whisper backend on Metal (Apple Silicon)
```bash
srt-gen input.mp4 --backend torch --device mps --model large-v3
```

### Specify source language (or keep auto-detect)
```bash
srt-gen input.mp4 --source-lang ja
```

### OpenAI backend
```bash
export OPENAI_API_KEY=your_key_here
srt-gen input.mp4 --backend openai --model whisper-1
```

Or pass API key directly:
```bash
srt-gen input.mp4 --backend openai --api-key your_key_here
```

### Silence progress output
```bash
srt-gen input.mp4 --quiet
```

## CLI Reference
```text
srt-gen input [-o output.srt]
  [--backend auto|local|mlx|torch|openai]
  [--model MODEL]
  [--source-lang LANG|auto]
  [--api-key KEY]
  [--ffmpeg-bin PATH]
  [--max-line-chars N]
  [--max-lines N]
  [--max-cps N]
  [--min-duration SECONDS]
  [--max-duration SECONDS]
  [--device auto|cpu|cuda|mps]
  [--compute-type TYPE]
  [--quiet]
```

### Arguments
- `input`
  - path to source video/audio file
- `-o, --output`
  - output `.srt` path
  - default: input path with `.srt` extension

### Backend and language
- `--backend`
  - `auto` (default), `local`, `mlx`, `torch`, or `openai`
- `--model`
  - auto/mlx default: `mlx-community/whisper-large-v3-mlx` (Apple Silicon)
  - local default: `large-v3` (non-Apple, or when `--backend local`)
  - torch default: `large-v3`
  - openai default: `whisper-1`
- `--source-lang`
  - source language code (for example `ja`, `fr`, `es`) or `auto` (default)
- `--api-key`
  - OpenAI API key (alternative to `OPENAI_API_KEY`)

### Subtitle shaping
- `--max-line-chars`
  - target max characters per line (default: `42`)
- `--max-lines`
  - max lines per cue (default: `2`)
- `--max-cps`
  - target max reading speed in characters per second (default: `20.0`)
- `--min-duration`
  - minimum cue duration in seconds (default: `1.0`)
- `--max-duration`
  - maximum cue duration in seconds (default: `6.0`)

### Runtime
- `--ffmpeg-bin`
  - ffmpeg executable name/path (default: `ffmpeg`)
- `--device`
  - local `faster-whisper` device: `auto`, `cpu`, or `cuda` (default: `auto`)
  - torch `openai-whisper` device: `auto`, `cpu`, `cuda`, or `mps`
- `--compute-type`
  - local `faster-whisper` compute type (default: `auto`)
- `--quiet`
  - disable progress/status messages

## Progress Output
By default, the CLI prints status updates to `stderr`:
- audio extraction start/finish
- transcription start/finish
- periodic segment progress (local backend)
- cue generation and file write

This is intended to show activity during long files/model initialization.

## How Translation Works
- Local backend calls Whisper with `task="translate"` (transcribe + translate to English in one pass).
- MLX backend calls Whisper with `task="translate"` (transcribe + translate to English in one pass).
- Torch backend calls OpenAI Whisper with `task="translate"` (transcribe + translate to English in one pass).
- OpenAI backend uses the audio translation endpoint.
- There is no separate post-translation step.

## Notes on Models
- On Apple Silicon with `--backend auto`, default model is `mlx-community/whisper-large-v3-mlx`.
- On non-Apple systems (or `--backend local`), default model is `large-v3`.
- On `--backend torch`, default model is `large-v3` and device can be `mps` on Apple Silicon.
- You can trade speed for accuracy with `--model medium` or smaller.
- First use of a local model may take longer due to model download.
- If language auto-detection is wrong, pass `--source-lang` explicitly (for example `ja`, `ko`, `fr`).
- MLX backend also accepts short aliases like `large-v3`, `medium`, `small`, and `turbo`.

## Troubleshooting

### `srt-gen: command not found`
Use one of:
```bash
source .venv/bin/activate
srt-gen input.mp4
```
or
```bash
.venv/bin/srt-gen input.mp4
```
or
```bash
python -m srt_gen input.mp4
```

### `ffmpeg was not found on PATH`
Install ffmpeg/ffprobe and ensure they are discoverable:
```bash
ffmpeg -version
ffprobe -version
```

### Long delay before first transcription
Expected on first run for a model: weights are downloaded/cached.

### Repeated word loops in output
If you see loops like `the the the the`, it is usually a decoding issue from the speech model (not SRT formatting).

What helps:
- Keep `--source-lang` explicit when auto-detection is unreliable.
- Try a stronger model (`--model large-v3` for local, or `mlx-community/whisper-large-v3-mlx` on Apple Silicon).
- Try another backend (`--backend local` vs `--backend mlx` vs `--backend torch`) for the same file.
- Improve audio quality before transcription (reduce background noise/music where possible).

`srt_gen` also applies a conservative cleanup pass that removes obvious single-word loops (3+ repeated words in a row) from backend text.

### OpenAI backend fails with API key error
Set key in environment or pass `--api-key`:
```bash
export OPENAI_API_KEY=your_key_here
```

### Generated subtitles are too dense or too short
Tune:
- `--max-line-chars`
- `--max-lines`
- `--max-cps`
- `--min-duration`
- `--max-duration`

## Development

### Project layout
```text
srt_gen/
  cli.py
  media.py
  segmentation.py
  srt_writer.py
  backends/
    base.py
    local_whisper.py
    mlx_whisper.py
    torch_whisper.py
    openai_api.py
```

### Local sanity checks
```bash
python -m compileall srt_gen
python -m srt_gen --help
```
