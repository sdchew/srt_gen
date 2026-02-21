from __future__ import annotations

import inspect
import platform
import re
from pathlib import Path
from typing import Any

from srt_gen.backends.base import ProgressCallback
from srt_gen.models import TranscriptSegment
from srt_gen.text_cleanup import collapse_repeated_word_loops


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
_UNEXPECTED_KWARG_RE = re.compile(r"unexpected keyword argument ['\"]([^'\"]+)['\"]")


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

    def _supported_transcribe_kwargs(
        self, transcribe_fn: Any, kwargs: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            signature = inspect.signature(transcribe_fn)
        except (TypeError, ValueError):
            return kwargs
        has_kwargs = any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in signature.parameters.values()
        )
        if has_kwargs:
            return kwargs
        supported = set(signature.parameters)
        return {key: value for key, value in kwargs.items() if key in supported}

    def _transcribe_with_kwarg_fallback(
        self,
        transcribe_fn: Any,
        audio_path: Path,
        kwargs: dict[str, Any],
        progress_callback: ProgressCallback | None,
    ) -> Any:
        active_kwargs = dict(kwargs)
        while True:
            try:
                return transcribe_fn(str(audio_path), **active_kwargs)
            except TypeError as exc:
                match = _UNEXPECTED_KWARG_RE.search(str(exc))
                if not match:
                    raise
                bad_key = match.group(1)
                if bad_key not in active_kwargs:
                    raise
                active_kwargs.pop(bad_key, None)
                if progress_callback:
                    progress_callback(
                        f"MLX backend does not support '{bad_key}'. Retrying without it."
                    )

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
            "condition_on_previous_text": False,
            "repetition_penalty": 1.1,
            "no_repeat_ngram_size": 3,
        }
        if source_language not in {"auto", "", None}:
            kwargs["language"] = source_language
        kwargs = self._supported_transcribe_kwargs(mlx_whisper.transcribe, kwargs)

        if progress_callback:
            progress_callback("Running MLX transcription...")
        result = self._transcribe_with_kwarg_fallback(
            mlx_whisper.transcribe,
            audio_path,
            kwargs,
            progress_callback,
        )

        segments_raw = _field(result, "segments", None) or []
        segments: list[TranscriptSegment] = []
        for seg in segments_raw:
            text = (_field(seg, "text", "") or "").strip()
            text = collapse_repeated_word_loops(text)
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
        text = collapse_repeated_word_loops(text)
        if not text:
            return []
        duration = float(_field(result, "duration", 0.0) or 0.0)
        if duration <= 0:
            duration = 5.0
        if progress_callback:
            progress_callback("MLX response did not include segments. Using single fallback cue.")
        return [TranscriptSegment(start=0.0, end=duration, text=text)]
