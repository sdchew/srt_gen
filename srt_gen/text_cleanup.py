from __future__ import annotations

import re

_STRIP_CHARS = ".,!?;:()[]{}\"'`"


def _normalize_word(word: str) -> str:
    return word.strip(_STRIP_CHARS).lower()


def collapse_repeated_word_loops(text: str, *, min_run: int = 3) -> str:
    """
    Collapse pathological repeated single-word runs (e.g. "the the the the")
    while preserving normal doubles such as "very very".
    """
    if min_run <= 2:
        min_run = 3
    words = text.split()
    if len(words) < min_run:
        return text.strip()

    out: list[str] = []
    i = 0
    total = len(words)
    while i < total:
        current = words[i]
        normalized = _normalize_word(current)
        if not normalized:
            out.append(current)
            i += 1
            continue

        j = i + 1
        while j < total and _normalize_word(words[j]) == normalized:
            j += 1

        run_len = j - i
        if run_len >= min_run:
            out.append(current)
        else:
            out.extend(words[i:j])
        i = j

    cleaned = " ".join(out).strip()
    return re.sub(r"\s+", " ", cleaned)
