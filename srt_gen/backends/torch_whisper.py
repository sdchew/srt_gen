from __future__ import annotations

from pathlib import Path
from typing import Any

from srt_gen.backends.base import ProgressCallback
from srt_gen.models import TranscriptSegment
from srt_gen.text_cleanup import collapse_repeated_word_loops


class TorchWhisperBackend:
    def __init__(self, *, model_name: str = "large-v3", device: str = "auto") -> None:
        self.model_name = model_name
        self.device = device
        self._model: Any | None = None
        self._resolved_device: str | None = None

    def _resolve_device(self, torch_module: Any) -> str:
        requested = (self.device or "auto").lower()
        valid = {"auto", "cpu", "cuda", "mps"}
        if requested not in valid:
            raise RuntimeError(
                f"Invalid device '{self.device}'. Use one of: auto, cpu, cuda, mps."
            )

        cuda_available = bool(getattr(torch_module, "cuda", None)) and bool(
            torch_module.cuda.is_available()
        )
        mps_backend = getattr(getattr(torch_module, "backends", None), "mps", None)
        mps_available = bool(mps_backend) and bool(mps_backend.is_available())

        if requested == "auto":
            if cuda_available:
                return "cuda"
            if mps_available:
                return "mps"
            return "cpu"

        if requested == "cuda" and not cuda_available:
            raise RuntimeError("CUDA device was requested but is not available.")
        if requested == "mps" and not mps_available:
            raise RuntimeError("MPS device was requested but is not available.")
        return requested

    def _get_model(self) -> tuple[Any, str]:
        if self._model is not None and self._resolved_device is not None:
            return self._model, self._resolved_device

        try:
            import torch  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "Missing dependency 'torch'. Install with: pip install -e '.[torch]'"
            ) from exc
        try:
            import whisper  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "Missing dependency 'openai-whisper'. Install with: pip install -e '.[torch]'"
            ) from exc

        device = self._resolve_device(torch)
        self._model = whisper.load_model(self.model_name, device=device)
        self._resolved_device = device
        return self._model, device

    def transcribe(
        self,
        audio_path: Path,
        source_language: str = "auto",
        progress_callback: ProgressCallback | None = None,
    ) -> list[TranscriptSegment]:
        if progress_callback:
            progress_callback(f"Loading torch Whisper model '{self.model_name}'...")
        model, device = self._get_model()
        if progress_callback:
            progress_callback(f"Model loaded on '{device}'. Running transcription...")

        kwargs: dict[str, Any] = {
            "task": "translate",
            "verbose": False,
            "condition_on_previous_text": False,
            # Keep FP16 scoped to CUDA for broad compatibility.
            "fp16": device == "cuda",
        }
        if source_language not in {"auto", "", None}:
            kwargs["language"] = source_language

        result = model.transcribe(str(audio_path), **kwargs)

        segments_raw = result.get("segments") if isinstance(result, dict) else None
        segments: list[TranscriptSegment] = []
        for seg in segments_raw or []:
            if not isinstance(seg, dict):
                continue
            text = (seg.get("text", "") or "").strip()
            text = collapse_repeated_word_loops(text)
            if not text:
                continue
            start = float(seg.get("start", 0.0) or 0.0)
            end = float(seg.get("end", start) or start)
            if end <= start:
                continue
            segments.append(TranscriptSegment(start=start, end=end, text=text))

        if segments:
            if progress_callback:
                progress_callback(f"Parsed {len(segments)} timestamped segments from torch Whisper.")
            return segments

        text = ""
        if isinstance(result, dict):
            text = (result.get("text", "") or "").strip()
        text = collapse_repeated_word_loops(text)
        if not text:
            return []

        duration = 5.0
        if isinstance(result, dict):
            duration = float(result.get("duration", 0.0) or 0.0) or duration
        if progress_callback:
            progress_callback(
                "Torch Whisper response did not include segments. Using single fallback cue."
            )
        return [TranscriptSegment(start=0.0, end=duration, text=text)]
