from dataclasses import dataclass


@dataclass(slots=True)
class TranscriptSegment:
    start: float
    end: float
    text: str


@dataclass(slots=True)
class SubtitleCue:
    start: float
    end: float
    text: str
