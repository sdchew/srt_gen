from __future__ import annotations

import math
import textwrap
from dataclasses import replace

from srt_gen.models import SubtitleCue, TranscriptSegment


def _split_words_evenly(words: list[str], parts: int) -> list[list[str]]:
    if parts <= 1 or len(words) <= 1:
        return [words]

    out: list[list[str]] = []
    total = len(words)
    for idx in range(parts):
        start = round(idx * total / parts)
        end = round((idx + 1) * total / parts)
        chunk = words[start:end]
        if chunk:
            out.append(chunk)
    return out or [words]


def _allocate_times(start: float, end: float, weights: list[int]) -> list[tuple[float, float]]:
    if end <= start:
        return []
    total = sum(max(w, 1) for w in weights)
    if total <= 0:
        total = len(weights)

    times: list[tuple[float, float]] = []
    cursor = start
    duration = end - start
    for i, weight in enumerate(weights):
        part = duration * (max(weight, 1) / total)
        nxt = end if i == len(weights) - 1 else cursor + part
        times.append((cursor, nxt))
        cursor = nxt
    return times


def build_cues(
    segments: list[TranscriptSegment],
    *,
    max_line_chars: int = 42,
    max_lines: int = 2,
    min_duration: float = 1.0,
    max_duration: float = 6.0,
) -> list[SubtitleCue]:
    max_line_chars = max(max_line_chars, 8)
    max_lines = max(max_lines, 1)
    max_chars_total = max_line_chars * max_lines
    max_duration = max(max_duration, 0.3)
    min_duration = max(min_duration, 0.1)
    if min_duration > max_duration:
        min_duration = max_duration

    raw_cues: list[SubtitleCue] = []
    for seg in sorted(segments, key=lambda s: (s.start, s.end)):
        text = " ".join(seg.text.split())
        if not text:
            continue
        start = max(float(seg.start), 0.0)
        end = max(float(seg.end), start + 0.1)

        words = text.split()
        pieces_needed = max(
            1,
            math.ceil((end - start) / max_duration),
            math.ceil(len(text) / max_chars_total),
        )
        word_groups = _split_words_evenly(words, pieces_needed)
        part_texts = [" ".join(group).strip() for group in word_groups if group]
        if not part_texts:
            continue

        part_weights = [len(part) for part in part_texts]
        part_times = _allocate_times(start, end, part_weights)
        if not part_times:
            continue

        for part_text, (part_start, part_end) in zip(part_texts, part_times, strict=False):
            lines = textwrap.wrap(
                part_text,
                width=max_line_chars,
                break_long_words=False,
                break_on_hyphens=False,
            )
            if not lines:
                lines = [part_text]

            line_groups = [lines[i : i + max_lines] for i in range(0, len(lines), max_lines)]
            group_texts = ["\n".join(group).strip() for group in line_groups if group]
            if not group_texts:
                continue

            group_weights = [len(group_text.replace("\n", " ")) for group_text in group_texts]
            group_times = _allocate_times(part_start, part_end, group_weights)
            for group_text, (cue_start, cue_end) in zip(group_texts, group_times, strict=False):
                raw_cues.append(SubtitleCue(start=cue_start, end=cue_end, text=group_text))

    if not raw_cues:
        return []

    cues: list[SubtitleCue] = []
    last_end = 0.0
    for cue in raw_cues:
        start = max(cue.start, last_end)
        end = max(cue.end, start + 0.1)
        duration = end - start
        if duration > max_duration:
            end = start + max_duration
            duration = max_duration
        if duration < min_duration:
            end = start + min_duration
        cues.append(replace(cue, start=start, end=end))
        last_end = end

    for idx in range(len(cues) - 1):
        current = cues[idx]
        nxt = cues[idx + 1]
        if current.end <= nxt.start:
            continue
        adjusted_end = max(current.start + 0.1, nxt.start)
        cues[idx] = replace(current, end=adjusted_end)
        if cues[idx].end <= cues[idx].start:
            cues[idx] = replace(cues[idx], end=cues[idx].start + 0.1)

    return cues
