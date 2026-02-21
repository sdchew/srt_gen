from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from srt_gen.backends.base import ProgressCallback
from srt_gen.models import TranscriptSegment
from srt_gen.text_cleanup import collapse_repeated_word_loops


def _field(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


class OpenAIBackend:
    def __init__(self, *, api_key: str | None = None, model_name: str = "whisper-1") -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model_name = model_name
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "Missing dependency 'openai'. Install with: pip install -e '.[openai]'"
            ) from exc
        if not self.api_key:
            raise RuntimeError("Missing OpenAI API key. Provide --api-key or OPENAI_API_KEY.")
        self._client = OpenAI(api_key=self.api_key)
        return self._client

    def transcribe(
        self,
        audio_path: Path,
        source_language: str = "auto",
        progress_callback: ProgressCallback | None = None,
    ) -> list[TranscriptSegment]:
        client = self._get_client()

        if progress_callback:
            progress_callback(f"Submitting audio to OpenAI model '{self.model_name}'...")
        with audio_path.open("rb") as audio_file:
            payload: dict[str, Any] = {
                "file": audio_file,
                "model": self.model_name,
                "response_format": "verbose_json",
            }
            if source_language not in {"auto", "", None}:
                payload["language"] = source_language
            response = client.audio.translations.create(**payload)
        if progress_callback:
            progress_callback("OpenAI response received. Processing segments...")

        segments_raw = _field(response, "segments", None) or []
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
                progress_callback(f"Parsed {len(segments)} timestamped segments from OpenAI.")
            return segments

        # Fallback when segment-level timestamps are not returned by the API.
        text = (_field(response, "text", "") or "").strip()
        text = collapse_repeated_word_loops(text)
        if not text:
            return []
        duration = float(_field(response, "duration", 0.0) or 0.0)
        if duration <= 0:
            duration = 5.0
        if progress_callback:
            progress_callback("OpenAI response did not include segments. Using single fallback cue.")
        return [TranscriptSegment(start=0.0, end=duration, text=text)]
