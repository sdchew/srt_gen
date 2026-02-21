from __future__ import annotations

import math
import textwrap

from srt_gen.models import SubtitleCue, TranscriptSegment

_PUNCTUATION_BREAK_CHARS = frozenset({".", ",", "!", "?", ";", ":", "…"})
_MIN_INTERNAL_DURATION = 0.12
_MIN_CUE_GAP = 0.04


def _timing_text_len(text: str) -> int:
    return max(len(text.replace("\n", " ").strip()), 1)


def _is_break_after(word: str) -> bool:
    cleaned = word.rstrip("\"')]} ")
    if not cleaned:
        return False
    return cleaned[-1] in _PUNCTUATION_BREAK_CHARS


def _split_words_by_breaks(words: list[str], parts: int) -> list[list[str]]:
    if parts <= 1 or len(words) <= 1:
        return [words]

    total = len(words)
    target_breaks = [round(total * k / parts) for k in range(1, parts)]
    punctuation_breaks = [idx for idx in range(1, total) if _is_break_after(words[idx - 1])]

    breakpoints: list[int] = []
    prev = 0
    for i, target in enumerate(target_breaks):
        low = prev + 1
        high = total - (len(target_breaks) - i)
        candidates = [bp for bp in punctuation_breaks if low <= bp <= high]
        if candidates:
            bp = min(candidates, key=lambda x: abs(x - target))
        else:
            bp = min(max(target, low), high)
        breakpoints.append(bp)
        prev = bp

    out: list[list[str]] = []
    start = 0
    for bp in breakpoints:
        chunk = words[start:bp]
        if chunk:
            out.append(chunk)
        start = bp
    tail = words[start:]
    if tail:
        out.append(tail)
    return out or [words]


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


def _preferred_duration(
    text: str,
    *,
    min_duration: float,
    max_duration: float,
    max_cps: float,
) -> float:
    cps = max(max_cps, 8.0)
    natural = _timing_text_len(text) / cps
    return min(max(natural, min_duration), max_duration)


def _retime_cues(
    cues: list[SubtitleCue],
    *,
    min_duration: float,
    max_duration: float,
    max_cps: float,
) -> list[SubtitleCue]:
    if not cues:
        return []

    sorted_cues = sorted(cues, key=lambda c: (c.start, c.end))
    starts: list[float] = []
    ends: list[float] = []
    base_starts: list[float] = []
    base_ends: list[float] = []
    texts: list[str] = []

    last_end = 0.0
    for cue in sorted_cues:
        base_start = max(float(cue.start), 0.0)
        base_end = max(float(cue.end), base_start + _MIN_INTERNAL_DURATION)
        start = max(base_start, last_end + (0.0 if not starts else _MIN_CUE_GAP))
        end = max(base_end, start + _MIN_INTERNAL_DURATION)
        starts.append(start)
        ends.append(end)
        base_starts.append(base_start)
        base_ends.append(base_end)
        texts.append(cue.text)
        last_end = end

    total = len(starts)
    timing_flex = max(0.18, min(0.45, min_duration * 0.3))

    for idx in range(total):
        start = starts[idx]
        end = ends[idx]
        target = _preferred_duration(
            texts[idx],
            min_duration=min_duration,
            max_duration=max_duration,
            max_cps=max_cps,
        )

        if end - start > max_duration:
            end = start + max_duration

        need = max(0.0, target - (end - start))
        if need > 0:
            next_limit = float("inf")
            if idx + 1 < total:
                next_limit = starts[idx + 1] - _MIN_CUE_GAP
            max_end = min(start + max_duration, next_limit, base_ends[idx] + timing_flex)
            forward_room = max(0.0, max_end - end)
            use_forward = min(forward_room, need)
            end += use_forward
            need -= use_forward

        if need > 0:
            prev_limit = 0.0
            if idx > 0:
                prev_limit = ends[idx - 1] + _MIN_CUE_GAP
            min_start = max(prev_limit, end - max_duration, base_starts[idx] - timing_flex)
            backward_room = max(0.0, start - min_start)
            use_backward = min(backward_room, need)
            start -= use_backward

        starts[idx] = start
        ends[idx] = max(end, start + _MIN_INTERNAL_DURATION)

    finalized: list[SubtitleCue] = []
    last_end = 0.0
    for idx, text in enumerate(texts):
        start = max(starts[idx], 0.0, last_end + (0.0 if idx == 0 else _MIN_CUE_GAP))
        end = max(ends[idx], start + _MIN_INTERNAL_DURATION)
        if end - start > max_duration:
            end = start + max_duration
        finalized.append(SubtitleCue(start=start, end=end, text=text))
        last_end = end

    return finalized


def build_cues(
    segments: list[TranscriptSegment],
    *,
    max_line_chars: int = 42,
    max_lines: int = 2,
    min_duration: float = 1.0,
    max_duration: float = 6.0,
    max_cps: float = 20.0,
) -> list[SubtitleCue]:
    max_line_chars = max(max_line_chars, 8)
    max_lines = max(max_lines, 1)
    max_chars_total = max_line_chars * max_lines
    max_duration = max(max_duration, 0.3)
    min_duration = max(min_duration, 0.1)
    max_cps = max(max_cps, 8.0)
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
        seg_duration = max(end - start, _MIN_INTERNAL_DURATION)
        seg_chars = _timing_text_len(text)
        pieces_needed = max(
            1,
            math.ceil(seg_duration / max_duration),
            math.ceil(seg_chars / max_chars_total),
            math.ceil(seg_chars / (max_cps * seg_duration)),
        )
        word_groups = _split_words_by_breaks(words, pieces_needed)
        if len(word_groups) < pieces_needed:
            word_groups = _split_words_evenly(words, pieces_needed)
        part_texts = [" ".join(group).strip() for group in word_groups if group]
        if not part_texts:
            continue

        part_weights = [_timing_text_len(part) for part in part_texts]
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

            group_weights = [_timing_text_len(group_text) for group_text in group_texts]
            group_times = _allocate_times(part_start, part_end, group_weights)
            for group_text, (cue_start, cue_end) in zip(group_texts, group_times, strict=False):
                raw_cues.append(SubtitleCue(start=cue_start, end=cue_end, text=group_text))

    if not raw_cues:
        return []

    return _retime_cues(
        raw_cues,
        min_duration=min_duration,
        max_duration=max_duration,
        max_cps=max_cps,
    )
