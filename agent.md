# Agent Guide: `srt_gen`

## Objective
Build a cross-platform Python CLI that generates English `.srt` subtitle files from video or audio input files.

## Product Decisions (Locked for v1)
- Transcription mode is local-first.
- Optional OpenAI API backend is supported when an API key is provided.
- Apple Silicon uses `mlx-whisper` in auto mode for faster local inference.
  - Default MLX model: `mlx-community/whisper-large-v3-mlx`
- Input/source language can be any language.
- Output language is always English.
- CLI should run on macOS, Linux, and Windows.

## Proposed CLI
```bash
srt-gen input.mp4 -o output.srt \
  --backend auto|local|mlx|openai \
  --model small \
  --source-lang auto \
  --max-line-chars 42 \
  --max-cps 20 \
  --max-duration 6.0 \
  --min-duration 1.0
```

## Recommended Stack
- Python 3.10+
- `ffmpeg` for media/audio extraction
- `faster-whisper` for local transcription/translation
- `mlx-whisper` for Apple Silicon optimized local transcription/translation
- OpenAI API client for optional cloud backend

## v1 Scope
1. Accept media input and extract normalized audio.
2. Transcribe/translate to English (auto backend: MLX on Apple Silicon, faster-whisper elsewhere).
3. Segment text into readable subtitle chunks.
4. Write standards-compliant `.srt` output.

## Suggested Project Structure
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
    openai_api.py
```

## Quality Defaults
- Max 2 lines per subtitle.
- Target line length around 42 chars.
- Subtitle duration range: 1.0s to 6.0s.
- No overlapping cues.

## Milestones
1. CLI skeleton + argument parsing.
2. Local backend end-to-end generation.
3. OpenAI backend integration.
4. Tests, packaging, and installability (`pipx`).
