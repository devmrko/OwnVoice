import importlib.util
from collections.abc import Callable
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from ownvoice.audio import RATE, Audio
from ownvoice.config import Settings
from ownvoice.telemetry import device_details


class Engine(Protocol):
    def synthesize(self, text: str, reference: Path, transcript: str, language: str) -> Audio: ...


def detect_device(requested: str = "auto") -> str:
    import torch

    available = ["cpu"]
    if torch.backends.mps.is_available():
        available.insert(0, "mps")
    if torch.cuda.is_available():
        available.insert(0, "cuda:0")
    if requested == "auto":
        return available[0]
    if requested == "cuda":
        requested = "cuda:0"
    if requested not in available:
        raise ValueError("요청한 실행 장치를 사용할 수 없습니다.")
    return requested


def runtime(settings: Settings) -> dict[str, Any]:
    installed = importlib.util.find_spec("qwen_tts") is not None
    try:
        device = detect_device(settings.device)
        error = None
    except (ImportError, ValueError) as exc:
        device = None
        error = "TTS 의존성을 설치해 주세요." if isinstance(exc, ImportError) else str(exc)
    try:
        engine_version = version("qwen-tts")
    except PackageNotFoundError:
        engine_version = None
    return {
        "engine": {"name": "Qwen3-TTS", "version": engine_version},
        "device": device,
        "hardware": device_details(device),
        "tts_installed": installed,
        "model": settings.model,
        "error": error,
        "inference_verified": False,
    }


class QwenEngine:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.model: Any = None
        self.prompts: dict[str, Any] = {}
        self.verified = False
        self.on_progress: Callable[[str], None] = lambda stage: None

    def synthesize(self, text: str, reference: Path, transcript: str, language: str) -> Audio:
        self.on_progress("initializing")
        import torch
        from qwen_tts import Qwen3TTSModel

        if self.model is None:
            self.on_progress("model_loading")
            device = detect_device(self.settings.device)
            dtype = (
                torch.bfloat16
                if device.startswith("cuda") and torch.cuda.is_bf16_supported()
                else torch.float32
            )
            self.model = Qwen3TTSModel.from_pretrained(
                self.settings.model, device_map=device, dtype=dtype, attn_implementation="eager"
            )
        key = str(reference)
        if key not in self.prompts:
            self.on_progress("voice_preparing")
            self.prompts[key] = self.model.create_voice_clone_prompt(
                ref_audio=key, ref_text=transcript or None, x_vector_only_mode=not bool(transcript)
            )
        self.on_progress("synthesizing")
        waves, rate = self.model.generate_voice_clone(
            text=text, language=language, voice_clone_prompt=self.prompts[key], max_new_tokens=2048
        )
        audio = np.asarray(waves[0], dtype=np.float32)
        if rate != RATE or audio.ndim != 1 or not len(audio) or not np.isfinite(audio).all():
            raise ValueError("Invalid model audio")
        self.verified = True
        return audio
