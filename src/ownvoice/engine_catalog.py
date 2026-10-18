import os
from pathlib import Path
from typing import Any

from ownvoice.config import Settings

SMALL_MODEL = "Qwen/Qwen3-TTS-12Hz-0.6B-Base"


def chatterbox_python() -> Path:
    default = Path("engines/chatterbox/.venv") / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    # Preserve the venv executable symlink: resolving it selects the base Python
    # and silently loses the isolated environment's installed packages.
    return Path(os.environ.get("OWNVOICE_CHATTERBOX_PYTHON", str(default))).absolute()


def engine_catalog(settings: Settings) -> list[dict[str, Any]]:
    return [
        {"id": "qwen", "name": "Qwen3-TTS · 1.7B", "model": settings.model, "available": True},
        {"id": "qwen-small", "name": "Qwen3-TTS · 0.6B", "model": SMALL_MODEL, "available": True},
        {
            "id": "chatterbox",
            "name": "Chatterbox Multilingual V3",
            "model": "ResembleAI/chatterbox · v3",
            "available": chatterbox_python().is_file(),
        },
    ]
