from argparse import Namespace
from types import SimpleNamespace

import pytest

from srt_gen.backends.torch_whisper import TorchWhisperBackend
from srt_gen.cli import _build_backend, build_parser


def _torch_available(*, cuda: bool, mps: bool) -> SimpleNamespace:
    return SimpleNamespace(
        cuda=SimpleNamespace(is_available=lambda: cuda),
        backends=SimpleNamespace(
            mps=SimpleNamespace(is_available=lambda: mps),
        ),
    )


def test_torch_backend_auto_prefers_cuda_then_mps() -> None:
    backend = TorchWhisperBackend(model_name="large-v3", device="auto")
    assert backend._resolve_device(_torch_available(cuda=True, mps=True)) == "cuda"
    assert backend._resolve_device(_torch_available(cuda=False, mps=True)) == "mps"
    assert backend._resolve_device(_torch_available(cuda=False, mps=False)) == "cpu"


def test_torch_backend_rejects_unavailable_explicit_device() -> None:
    backend = TorchWhisperBackend(model_name="large-v3", device="mps")
    with pytest.raises(RuntimeError, match="MPS device was requested"):
        backend._resolve_device(_torch_available(cuda=False, mps=False))


def test_build_backend_selects_torch_backend() -> None:
    args = Namespace(
        backend="torch",
        model="large-v3",
        api_key=None,
        device="mps",
        compute_type="auto",
    )
    name, backend = _build_backend(args)
    assert name == "torch"
    assert isinstance(backend, TorchWhisperBackend)
    assert backend.device == "mps"


def test_parser_accepts_torch_backend_and_mps_device() -> None:
    args = build_parser().parse_args(["input.mp4", "--backend", "torch", "--device", "mps"])
    assert args.backend == "torch"
    assert args.device == "mps"
