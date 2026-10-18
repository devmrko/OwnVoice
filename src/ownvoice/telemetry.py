"""Measured device and synthesis data; no cross-device benchmark assumptions."""

import platform
import subprocess
from functools import lru_cache
from typing import Any


@lru_cache(maxsize=4)
def device_details(device: str | None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "name": "장치 미확인",
        "backend": device,
        "memory_gb": None,
        "memory_kind": None,
    }
    if device is None:
        return result
    if device.startswith("cuda"):
        import torch

        props = torch.cuda.get_device_properties(device)
        result.update(name=props.name, memory_gb=round(props.total_memory / 1024**3, 1), memory_kind="VRAM")
    elif platform.system() == "Darwin":

        def sysctl(key: str) -> str:
            return subprocess.check_output(["/usr/sbin/sysctl", "-n", key], text=True, timeout=3).strip()

        try:
            chip = sysctl("machdep.cpu.brand_string")
            result.update(
                name=chip if device == "mps" else f"{chip} · CPU",
                memory_gb=round(int(sysctl("hw.memsize")) / 1024**3, 1),
                memory_kind="시스템 메모리 · 공유",
            )
        except (OSError, ValueError, subprocess.SubprocessError):
            result["name"] = "Apple Silicon" if device == "mps" else "CPU"
    else:
        result["name"] = platform.processor() or "CPU"
    return result


def performance(job: dict[str, Any]) -> dict[str, Any]:
    timings = job.get("synthesis_timings", [])
    generated = sum(t["seconds"] for t in timings)
    # New records carry audio_seconds. Legacy records can only be paired when
    # every synthesized result has a corresponding segment duration and no cache.
    if timings and all("audio_seconds" in t for t in timings):
        audio = sum(t["audio_seconds"] for t in timings)
    else:
        finished = [s for s in job["segments"] if s.get("duration_ms") is not None]
        audio = sum(s["duration_ms"] / 1000 for s in finished) if len(finished) == len(timings) else 0
    rtf = generated / audio if audio > 0 and generated > 0 else None
    return {
        "samples": len(timings),
        "synthesis_seconds": generated if timings else None,
        "audio_seconds": audio or None,
        "rtf": rtf,
        "audio_seconds_per_second": 1 / rtf if rtf else None,
        "first_segment_seconds": timings[0]["seconds"] if timings else None,
        "first_audio_ready_seconds": job.get("first_audio_ready_seconds"),
        "phase_seconds": job.get("phase_seconds", {}),
        "device": job.get("execution_device"),
    }
