"""Isolated Chatterbox JSON-lines worker. Run using its separate Python environment."""

import contextlib
import json
import sys
import traceback
from typing import Any


def emit(value: dict[str, Any]) -> None:
    print(json.dumps(value), flush=True)


def main() -> None:
    model: Any = None
    reference = None
    for line in sys.stdin:
        request = json.loads(line)
        try:
            emit({"stage": "initializing"})
            with contextlib.redirect_stdout(sys.stderr):
                import soundfile as sf
                import torch
                from chatterbox.mtl_tts import ChatterboxMultilingualTTS
            if model is None:
                emit({"stage": "model_loading"})
                with contextlib.redirect_stdout(sys.stderr):
                    model = ChatterboxMultilingualTTS.from_pretrained(device=request["device"], t3_model="v3")
                if str(model.device) != request["device"]:
                    raise RuntimeError("Chatterbox device differs from requested device")
            if reference != request["reference"]:
                emit({"stage": "voice_preparing"})
                with contextlib.redirect_stdout(sys.stderr):
                    model.prepare_conditionals(request["reference"])
                reference = request["reference"]
            emit({"stage": "synthesizing"})
            with contextlib.redirect_stdout(sys.stderr):
                wave = model.generate(request["text"], language_id=request["language"])
                wave = wave.squeeze().detach().cpu().numpy()
                sf.write(request["output"], wave, model.sr, subtype="PCM_16")
                if request["device"] == "mps":
                    torch.mps.synchronize()
            emit({"done": True})
        except Exception as exc:
            traceback.print_exc(file=sys.stderr)
            emit({"error": f"{type(exc).__name__}: {exc}"})


if __name__ == "__main__":
    main()
