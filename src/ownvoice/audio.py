import os
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf
from numpy.typing import NDArray

Audio = NDArray[np.float32]
RATE = 24000


class TimingOverflow(Exception):
    pass


def convert_reference(source: Path, target: Path) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-y",
            "-i",
            str(source),
            "-t",
            "61",
            "-ac",
            "1",
            "-ar",
            str(RATE),
            str(target),
        ],
        check=True,
        capture_output=True,
        timeout=60,
    )
    samples, rate = sf.read(target, dtype="float32")
    duration = len(samples) / rate
    if not 3 <= duration <= 60 or not np.isfinite(samples).all() or float(np.max(np.abs(samples))) < 0.001:
        raise ValueError("참조 음성은 무음이 아닌 3~60초 녹음이어야 합니다.")


def write_atomic(path: Path, audio: Audio, rate: int = RATE) -> None:
    temporary = path.with_suffix(".tmp.wav")
    sf.write(temporary, audio, rate, subtype="PCM_16")
    os.replace(temporary, path)


def fit_audio(raw: Path, target_samples: int, max_speed: float) -> tuple[Audio, float]:
    audio, rate = sf.read(raw, dtype="float32")
    if rate != RATE or audio.ndim != 1 or not len(audio) or not np.isfinite(audio).all():
        raise ValueError("Invalid generated audio")
    if len(audio) <= target_samples:
        return audio, 1.0
    speed = len(audio) / target_samples
    if speed > max_speed:
        raise TimingOverflow()
    # Ask ffmpeg for a slight margin; do not truncate its output to force a fit.
    adjusted = raw.with_suffix(".fit.wav")
    for factor in (speed * 1.005, speed * 1.015):
        if factor > max_speed:
            factor = max_speed
        subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-v",
                "error",
                "-y",
                "-i",
                str(raw),
                "-af",
                f"atempo={factor}",
                str(adjusted),
            ],
            check=True,
            capture_output=True,
            timeout=60,
        )
        fitted, _ = sf.read(adjusted, dtype="float32")
        if len(fitted) <= target_samples:
            return np.asarray(fitted, dtype=np.float32), factor
    raise TimingOverflow()
