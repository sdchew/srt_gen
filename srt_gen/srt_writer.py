from __future__ import annotations

from pathlib import Path

from srt_gen.models import SubtitleCue


def format_srt_timestamp(seconds: float) -> str:
    ms_total = max(0, int(round(seconds * 1000)))
    hours = ms_total // 3_600_000
    remainder = ms_total % 3_600_000
    minutes = remainder // 60_000
    remainder %= 60_000
    secs = remainder // 1000
    millis = remainder % 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def write_srt(cues: list[SubtitleCue], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for idx, cue in enumerate(cues, start=1):
            start = format_srt_timestamp(cue.start)
            end = format_srt_timestamp(cue.end)
            text = cue.text.strip()
            handle.write(f"{idx}\n{start} --> {end}\n{text}\n\n")
