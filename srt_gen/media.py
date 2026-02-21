from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


def extract_audio(
    input_path: Path,
    *,
    ffmpeg_bin: str = "ffmpeg",
    work_dir: Path | None = None,
) -> Path:
    """Extract mono 16k WAV audio from input media."""
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    run_dir = work_dir or Path(tempfile.mkdtemp(prefix="srt-gen-"))
    run_dir.mkdir(parents=True, exist_ok=True)
    output_path = run_dir / f"{input_path.stem}.wav"

    cmd = [
        ffmpeg_bin,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(input_path),
        "-ac",
        "1",
        "-ar",
        "16000",
        "-vn",
        "-sn",
        "-dn",
        str(output_path),
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        detail = stderr or f"{ffmpeg_bin} exited with code {proc.returncode}"
        raise RuntimeError(f"Audio extraction failed: {detail}")

    if not output_path.exists():
        raise RuntimeError("Audio extraction did not create output file.")
    return output_path
