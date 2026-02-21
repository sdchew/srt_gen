from __future__ import annotations

import platform
from pathlib import Path
from typing import Any

from srt_gen.backends.base import ProgressCallback
from srt_gen.models import TranscriptSegment


MLX_MODEL_ALIASES: dict[str, str] = {
    "tiny": "mlx-community/whisper-tiny-mlx",
    "base": "mlx-community/whisper-base-mlx",
    "small": "mlx-community/whisper-small-mlx",
    "medium": "mlx-community/whisper-medium-mlx",
    "large": "mlx-community/whisper-large-mlx",
    "large-v2": "mlx-community/whisper-large-v2-mlx",
    "large-v3": "mlx-community/whisper-large-v3-mlx",
    "large-v3-turbo": "mlx-community/whisper-large-v3-turbo",
    "turbo": "mlx-community/whisper-turbo",
}


def _field(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _resolve_model_name(model_name: str) -> str:
    value = (model_name or "").strip()
    if not value:
        return "mlx-community/whisper-large-v3-mlx"
    if "/" in value:
        return value
    return MLX_MODEL_ALIASES.get(value, value)


class MLXWhisperBackend:
    def __init__(self, *, model_name: str = "mlx-community/whisper-large-v3-mlx") -> None:
        self.model_name = _resolve_model_name(model_name)
        self._module: Any | None = None

    def _get_module(self) -> Any:
        if self._module is not None:
            return self._module

        system = platform.system()
        machine = platform.machine().lower()
        if system != "Darwin" or machine != "arm64":
            raise RuntimeError("MLX backend is only supported on Apple Silicon macOS (arm64).")

        try:
            import mlx_whisper  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "Missing dependency 'mlx-whisper'. On Apple Silicon run: ./setup_env.sh"
            ) from exc

        self._module = mlx_whisper
        return self._module

    def transcribe(
        self,
        audio_path: Path,
        source_language: str = "auto",
        progress_callback: ProgressCallback | None = None,
    ) -> list[TranscriptSegment]:
        if progress_callback:
            progress_callback(f"Loading MLX model '{self.model_name}'...")

        mlx_whisper = self._get_module()

        kwargs: dict[str, Any] = {
            "path_or_hf_repo": self.model_name,
            "task": "translate",
            "verbose": False,
        }
        if source_language not in {"auto", "", None}:
            kwargs["language"] = source_language

        if progress_callback:
            progress_callback("Running MLX transcription...")
        result = mlx_whisper.transcribe(str(audio_path), **kwargs)

        segments_raw = _field(result, "segments", None) or []
        segments: list[TranscriptSegment] = []
        for seg in segments_raw:
            text = (_field(seg, "text", "") or "").strip()
            if not text:
                continue
            start = float(_field(seg, "start", 0.0))
            end = float(_field(seg, "end", start))
            if end <= start:
                continue
            segments.append(TranscriptSegment(start=start, end=end, text=text))

        if segments:
            if progress_callback:
                progress_callback(f"Parsed {len(segments)} timestamped segments from MLX.")
            return segments

        text = (_field(result, "text", "") or "").strip()
        if not text:
            return []
        duration = float(_field(result, "duration", 0.0) or 0.0)
        if duration <= 0:
            duration = 5.0
        if progress_callback:
            progress_callback("MLX response did not include segments. Using single fallback cue.")
        return [TranscriptSegment(start=0.0, end=duration, text=text)]
