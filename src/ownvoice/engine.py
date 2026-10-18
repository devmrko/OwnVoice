import gc
import importlib.util
import json
import os
import subprocess
import tempfile
from collections.abc import Callable
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Protocol, TextIO

import numpy as np
import soundfile as sf

from ownvoice.audio import RATE, Audio
from ownvoice.config import Settings
from ownvoice.engine_catalog import SMALL_MODEL, chatterbox_python, engine_catalog
from ownvoice.telemetry import device_details


class Engine(Protocol):
    def synthesize(self, text: str, reference: Path, transcript: str, language: str) -> Audio: ...


def detect_device(requested: str = "auto") -> str:
    import torch

    available = ["cpu"]
    mps = getattr(torch.backends, "mps", None)
    if mps is not None and mps.is_available():
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
        "engines": engine_catalog(settings),
    }


class QwenEngine:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.model: Any = None
        self.prompts: dict[str, Any] = {}
        self.verified = False
        self.on_progress: Callable[[str], None] = lambda stage: None
        self.selected = "qwen"
        self.active_model = settings.model
        self.process: subprocess.Popen[str] | None = None
        self.log: TextIO | None = None

    def close(self) -> None:
        if self.process is not None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            if self.process.stdin:
                self.process.stdin.close()
            if self.process.stdout:
                self.process.stdout.close()
            self.process = None
        if self.log:
            self.log.close()
            self.log = None
        self.model = None
        self.prompts.clear()
        gc.collect()
        if importlib.util.find_spec("torch"):
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
                torch.mps.empty_cache()

    def select(self, engine: str) -> None:
        if engine not in {"qwen", "qwen-small", "chatterbox"}:
            raise ValueError("Unknown engine")
        if engine != self.selected:
            self.close()
            self.verified = False
            self.selected = engine
            self.active_model = SMALL_MODEL if engine == "qwen-small" else self.settings.model

    def chatterbox(self, text: str, reference: Path, language: str) -> Audio:
        languages = {"Korean": "ko", "English": "en", "Japanese": "ja", "Chinese": "zh"}
        if language not in languages:
            raise ValueError("Chatterbox requires an explicit language")
        if self.process is None or self.process.poll() is not None:
            self.close()
            folder = self.settings.data_dir / "logs"
            folder.mkdir(exist_ok=True)
            self.log = (folder / "chatterbox.log").open("a", encoding="utf-8")
            self.process = subprocess.Popen(
                [str(chatterbox_python()), str(Path(__file__).with_name("chatterbox_runner.py"))],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=self.log,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONUTF8": "1"},
            )
        with tempfile.TemporaryDirectory(dir=self.settings.data_dir) as temporary:
            output = Path(temporary).resolve() / "audio.wav"
            assert self.process.stdin is not None and self.process.stdout is not None
            self.process.stdin.write(
                json.dumps(
                    {
                        "text": text,
                        "reference": str(reference.resolve()),
                        "output": str(output),
                        "device": detect_device(self.settings.device),
                        "language": languages[language],
                    }
                )
                + "\n"
            )
            self.process.stdin.flush()
            for line in self.process.stdout:
                message = json.loads(line)
                if "stage" in message:
                    self.on_progress(message["stage"])
                elif "error" in message:
                    raise RuntimeError(message["error"])
                elif message.get("done"):
                    wave, rate = sf.read(output, dtype="float32")
                    if rate != RATE or wave.ndim != 1 or not len(wave) or not np.isfinite(wave).all():
                        raise ValueError("Invalid Chatterbox audio")
                    self.verified = True
                    return np.asarray(wave, dtype=np.float32)
            raise RuntimeError("Chatterbox process exited; see .data/logs/chatterbox.log")

    def synthesize(self, text: str, reference: Path, transcript: str, language: str) -> Audio:
        if self.selected == "chatterbox":
            return self.chatterbox(text, reference, language)
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
                self.active_model, device_map=device, dtype=dtype, attn_implementation="eager"
            )
        key = str(reference) + "\0" + transcript
        if key not in self.prompts:
            self.on_progress("voice_preparing")
            self.prompts[key] = self.model.create_voice_clone_prompt(
                ref_audio=str(reference), ref_text=transcript or None, x_vector_only_mode=not bool(transcript)
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
