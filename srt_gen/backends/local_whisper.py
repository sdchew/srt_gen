from __future__ import annotations

from pathlib import Path
from typing import Any

from srt_gen.backends.base import ProgressCallback
from srt_gen.models import TranscriptSegment


class LocalWhisperBackend:
    def __init__(
        self,
        *,
        model_name: str = "large-v3",
        device: str = "auto",
        compute_type: str = "auto",
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self._model: Any | None = None

    def _get_model(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError(
                "Missing dependency 'faster-whisper'. Install with: pip install -e ."
            ) from exc

        self._model = WhisperModel(
            self.model_name,
            device=self.device,
            compute_type=self.compute_type,
        )
        return self._model

    def transcribe(
        self,
        audio_path: Path,
        source_language: str = "auto",
        progress_callback: ProgressCallback | None = None,
    ) -> list[TranscriptSegment]:
        if progress_callback:
            progress_callback(f"Loading local model '{self.model_name}'...")
        model = self._get_model()
        if progress_callback:
            progress_callback("Model loaded. Running transcription...")
        language = None if source_language in {"auto", "", None} else source_language

        segments_iter, _ = model.transcribe(
            str(audio_path),
            task="translate",
            language=language,
            beam_size=5,
            vad_filter=True,
        )

        segments: list[TranscriptSegment] = []
        seen_segments = 0
        for seg in segments_iter:
            text = (getattr(seg, "text", "") or "").strip()
            if not text:
                continue
            start = float(getattr(seg, "start", 0.0))
            end = float(getattr(seg, "end", start))
            if end <= start:
                continue
            seen_segments += 1
            segments.append(TranscriptSegment(start=start, end=end, text=text))
            if progress_callback and (seen_segments == 1 or seen_segments % 10 == 0):
                progress_callback(
                    f"Transcribed {seen_segments} segments (up to {end:.1f}s audio)."
                )
        if progress_callback:
            progress_callback(f"Transcription stream complete ({seen_segments} segments).")
        return segments
