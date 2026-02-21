from pathlib import Path

import pytest

from srt_gen.backends.mlx_whisper import MLXWhisperBackend


def test_transcribe_with_kwarg_fallback_retries_without_unsupported_kwargs() -> None:
    backend = MLXWhisperBackend(model_name="large-v3")
    seen_calls: list[dict[str, object]] = []

    def fake_transcribe(path: str, **kwargs: object) -> dict[str, object]:
        assert path == "sample.wav"
        seen_calls.append(dict(kwargs))
        if "repetition_penalty" in kwargs:
            raise TypeError(
                "DecodingOptions.__init__() got an unexpected keyword argument 'repetition_penalty'"
            )
        if "no_repeat_ngram_size" in kwargs:
            raise TypeError(
                "DecodingOptions.__init__() got an unexpected keyword argument 'no_repeat_ngram_size'"
            )
        return {"text": "ok"}

    progress_messages: list[str] = []
    result = backend._transcribe_with_kwarg_fallback(
        fake_transcribe,
        Path("sample.wav"),
        {
            "task": "translate",
            "repetition_penalty": 1.1,
            "no_repeat_ngram_size": 3,
        },
        progress_messages.append,
    )

    assert result == {"text": "ok"}
    assert seen_calls[0]["repetition_penalty"] == 1.1
    assert seen_calls[1]["no_repeat_ngram_size"] == 3
    assert "repetition_penalty" not in seen_calls[-1]
    assert "no_repeat_ngram_size" not in seen_calls[-1]
    assert any("repetition_penalty" in msg for msg in progress_messages)
    assert any("no_repeat_ngram_size" in msg for msg in progress_messages)


def test_transcribe_with_kwarg_fallback_reraises_other_type_errors() -> None:
    backend = MLXWhisperBackend(model_name="large-v3")

    def fake_transcribe(_: str, **__: object) -> dict[str, object]:
        raise TypeError("bad input data")

    with pytest.raises(TypeError, match="bad input data"):
        backend._transcribe_with_kwarg_fallback(
            fake_transcribe,
            Path("sample.wav"),
            {"task": "translate"},
            None,
        )
