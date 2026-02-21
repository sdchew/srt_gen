from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from srt_gen.models import TranscriptSegment

ProgressCallback = Callable[[str], None]


class TranscriptionBackend(Protocol):
    def transcribe(
        self,
        audio_path: Path,
        source_language: str = "auto",
        progress_callback: ProgressCallback | None = None,
    ) -> list[TranscriptSegment]:
        """Transcribe audio and return timed text segments."""
