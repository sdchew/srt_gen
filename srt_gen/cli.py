from __future__ import annotations

import argparse
import platform
import sys
import tempfile
import time
from pathlib import Path

from srt_gen.backends.local_whisper import LocalWhisperBackend
from srt_gen.backends.mlx_whisper import MLXWhisperBackend
from srt_gen.backends.openai_api import OpenAIBackend
from srt_gen.backends.torch_whisper import TorchWhisperBackend
from srt_gen.media import extract_audio
from srt_gen.segmentation import build_cues
from srt_gen.srt_writer import write_srt


def _default_output_for(input_path: Path) -> Path:
    return input_path.with_suffix(".srt")


def _status(message: str, *, quiet: bool) -> None:
    if quiet:
        return
    print(f"[srt-gen] {message}", file=sys.stderr, flush=True)


def _is_apple_silicon() -> bool:
    return platform.system() == "Darwin" and platform.machine().lower() == "arm64"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srt-gen",
        description="Generate English .srt subtitles from video/audio files.",
    )
    parser.add_argument("input", type=Path, help="Input media file path")
    parser.add_argument("-o", "--output", type=Path, help="Output .srt file path")

    parser.add_argument(
        "--backend",
        choices=["auto", "local", "mlx", "torch", "openai"],
        default="auto",
    )
    parser.add_argument("--model", help="Model name for selected backend")
    parser.add_argument("--source-lang", default="auto", help="Source language code or 'auto'")
    parser.add_argument("--api-key", help="OpenAI API key (for openai backend)")

    parser.add_argument("--ffmpeg-bin", default="ffmpeg", help="ffmpeg binary path")
    parser.add_argument("--max-line-chars", type=int, default=42)
    parser.add_argument("--max-lines", type=int, default=2)
    parser.add_argument("--max-cps", type=float, default=20.0, help="Max subtitle reading speed (chars/sec)")
    parser.add_argument("--min-duration", type=float, default=1.0)
    parser.add_argument("--max-duration", type=float, default=6.0)

    parser.add_argument(
        "--device",
        default="auto",
        help="Backend device (auto/cpu/cuda). Torch backend also supports mps.",
    )
    parser.add_argument("--compute-type", default="auto", help="Local backend compute type")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress/status messages")
    return parser


def _build_backend(args: argparse.Namespace):
    if args.backend == "openai":
        model = args.model or "whisper-1"
        return "openai", OpenAIBackend(api_key=args.api_key, model_name=model)

    if args.backend == "torch":
        model = args.model or "large-v3"
        return "torch", TorchWhisperBackend(model_name=model, device=args.device)

    if args.backend == "mlx":
        model = args.model or "mlx-community/whisper-large-v3-mlx"
        return "mlx", MLXWhisperBackend(model_name=model)

    if args.backend == "auto" and _is_apple_silicon():
        if args.model and "/" not in args.model and not args.model.startswith("mlx-"):
            return "local", LocalWhisperBackend(
                model_name=args.model,
                device=args.device,
                compute_type=args.compute_type,
            )
        model = args.model or "mlx-community/whisper-large-v3-mlx"
        return "mlx", MLXWhisperBackend(model_name=model)

    model = args.model or "large-v3"
    return "local", LocalWhisperBackend(
        model_name=model, device=args.device, compute_type=args.compute_type
    )


def run(args: argparse.Namespace) -> int:
    total_start = time.monotonic()
    input_path: Path = args.input.expanduser().resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    output_path = (args.output or _default_output_for(input_path)).expanduser().resolve()
    backend_name, backend = _build_backend(args)
    _status(f"Input: {input_path}", quiet=args.quiet)
    _status(f"Output: {output_path}", quiet=args.quiet)
    _status(f"Backend: {backend_name}", quiet=args.quiet)

    with tempfile.TemporaryDirectory(prefix="srt-gen-") as tmp_dir:
        extract_start = time.monotonic()
        _status("Extracting audio with ffmpeg...", quiet=args.quiet)
        audio_path = extract_audio(
            input_path=input_path,
            ffmpeg_bin=args.ffmpeg_bin,
            work_dir=Path(tmp_dir),
        )
        extract_elapsed = time.monotonic() - extract_start
        _status(f"Audio extraction complete ({extract_elapsed:.1f}s).", quiet=args.quiet)

        _status("Transcribing and translating to English...", quiet=args.quiet)
        transcribe_start = time.monotonic()
        progress_callback = None if args.quiet else (lambda msg: _status(msg, quiet=False))
        segments = backend.transcribe(
            audio_path,
            source_language=args.source_lang,
            progress_callback=progress_callback,
        )
        transcribe_elapsed = time.monotonic() - transcribe_start
        _status(
            f"Transcription complete ({len(segments)} segments, {transcribe_elapsed:.1f}s).",
            quiet=args.quiet,
        )

    cue_start = time.monotonic()
    _status("Building subtitle cues...", quiet=args.quiet)
    cues = build_cues(
        segments,
        max_line_chars=args.max_line_chars,
        max_lines=args.max_lines,
        max_cps=args.max_cps,
        min_duration=args.min_duration,
        max_duration=args.max_duration,
    )
    cue_elapsed = time.monotonic() - cue_start
    _status(f"Cue generation complete ({len(cues)} cues, {cue_elapsed:.1f}s).", quiet=args.quiet)

    _status("Writing SRT file...", quiet=args.quiet)
    write_srt(cues, output_path)
    total_elapsed = time.monotonic() - total_start

    print(f"Wrote {len(cues)} subtitle cues to {output_path} ({total_elapsed:.1f}s)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
