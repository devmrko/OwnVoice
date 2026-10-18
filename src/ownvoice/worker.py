import json
import logging
import os
import threading
import time
from typing import Any

import numpy as np
import soundfile as sf
from filelock import FileLock

from ownvoice.audio import RATE, TimingOverflow, fit_audio, write_atomic
from ownvoice.engine import Engine, QwenEngine, detect_device
from ownvoice.service import Service
from ownvoice.telemetry import device_details


def process_job(service: Service, engine: Engine, job: dict[str, Any]) -> None:
    key = job["id"]
    folder = service.settings.data_dir / "jobs" / key
    folder.mkdir(exist_ok=True)
    profile = service.get("profile", job["profile_id"])
    reference = service.settings.data_dir / "profiles" / profile["id"] / "reference.wav"
    staged = folder / "output.tmp.wav"
    review = False
    job.setdefault("started_at", time.time())
    job.setdefault("synthesis_timings", [])
    synthesis_started = None
    phase_started = time.monotonic()
    current_phase = "preparing"
    job["phase_seconds"] = {}

    def stage(name: str) -> None:
        nonlocal synthesis_started, phase_started, current_phase
        now = time.monotonic()
        phases = job["phase_seconds"]
        phases[current_phase] = phases.get(current_phase, 0.0) + now - phase_started
        current_phase, phase_started = name, now
        job.update(stage=name, stage_started_at=time.time())
        if name == "synthesizing":
            synthesis_started = time.monotonic()
        service.update_job(key, job)

    if isinstance(engine, QwenEngine):
        engine.on_progress = stage
    try:
        if isinstance(engine, QwenEngine):
            job["execution_device"] = device_details(detect_device(service.settings.device))
        with sf.SoundFile(staged, "w", samplerate=RATE, channels=1, subtype="PCM_16") as output:
            for segment in job["segments"]:
                job["current_segment"] = segment["index"] + 1
                raw = folder / f"{segment['index']}.wav"
                limit = service.settings.srt_max_attempts if job["mode"] == "srt" else 1
                segment.setdefault("synthesis_attempts", 0)
                segment["timing_error"] = None
                job.update(current_attempt=segment["synthesis_attempts"], attempt_limit=limit)
                regenerate = not raw.exists() or (
                    segment["status"] == "pending" and segment["synthesis_attempts"] == 0
                )
                while True:
                    if regenerate:
                        segment["synthesis_attempts"] += 1
                        job.update(current_attempt=segment["synthesis_attempts"], attempt_limit=limit)
                        stage("initializing" if isinstance(engine, QwenEngine) else "synthesizing")
                        samples = engine.synthesize(
                            segment["text"], reference, profile["transcript"], job["language"]
                        )
                        if synthesis_started is not None:
                            job["synthesis_timings"].append(
                                {
                                    "seconds": time.monotonic() - synthesis_started,
                                    "chars": len(segment["text"]),
                                    "audio_seconds": len(samples) / RATE,
                                    "segment_index": segment["index"],
                                }
                            )
                        if job.get("first_audio_ready_seconds") is None:
                            job["first_audio_ready_seconds"] = time.time() - job["started_at"]
                        # Keep the shortest whole candidate, never truncate speech.
                        if not raw.exists() or len(samples) < sf.info(raw).frames:
                            write_atomic(raw, samples)
                    stage("fitting")
                    samples, _ = sf.read(raw, dtype="float32")
                    segment["duration_ms"] = round(len(samples) * 1000 / RATE)
                    segment["speed"] = 1.0
                    if job["mode"] != "srt":
                        break
                    start = round(segment["start_ms"] * RATE / 1000)
                    end = round(segment["end_ms"] * RATE / 1000)
                    try:
                        samples, speed = fit_audio(raw, end - start, service.settings.max_speed)
                        segment["speed"] = speed
                        break
                    except TimingOverflow:
                        if segment["synthesis_attempts"] < limit:
                            regenerate = True
                            continue
                        available = (end - start) / RATE
                        segment["status"] = "needs_review"
                        segment["timing_error"] = (
                            f"{segment['synthesis_attempts']}회 시도 · 배정 {available:.2f}초 · "
                            f"최단 음성 {segment['duration_ms'] / 1000:.2f}초 · "
                            f"최대 {service.settings.max_speed:.2f}배 가속으로 맞출 수 없습니다."
                        )
                        review = True
                        service.update_job(key, job)
                        break
                if segment["timing_error"] is not None:
                    continue
                if job["mode"] == "srt":
                    # Write bounded silence chunks to keep long SRTs memory-safe.
                    gap = start - output.tell()
                    while gap > 0:
                        chunk = min(gap, RATE * 10)
                        output.write(np.zeros(chunk, dtype=np.float32))
                        gap -= chunk
                    output.write(samples)
                    remaining = end - output.tell()
                    while remaining > 0:
                        chunk = min(remaining, RATE * 10)
                        output.write(np.zeros(chunk, dtype=np.float32))
                        remaining -= chunk
                else:
                    output.write(samples)
                    if segment["index"] < len(job["segments"]) - 1:
                        output.write(np.zeros(int(0.2 * RATE), dtype=np.float32))
                segment["status"] = "completed"
                service.update_job(key, job)
        stage("saving")
        if review:
            staged.unlink(missing_ok=True)
            job["status"] = "needs_review"
            job["error"] = (
                "자동 재시도 후에도 시간을 초과한 구간이 있습니다. 구간별 배정 시간과 음성 길이를 확인해 주세요."
            )
        else:
            os.replace(staged, folder / "output.wav")
            job["status"] = "completed"
        stage(job["status"])
        job.update(stage=job["status"], finished_at=time.time(), current_segment=None)
        service.update_job(key, job)
    except Exception as exc:
        staged.unlink(missing_ok=True)
        logging.getLogger(__name__).error("TTS job failed: %s", type(exc).__name__)
        job.update(
            status="failed",
            stage="failed",
            finished_at=time.time(),
            error=f"음성 생성 실패 ({type(exc).__name__}). TTS 설치·모델·실행 장치를 확인하고 재시도해 주세요.",
        )
        service.update_job(key, job)
    finally:
        if isinstance(engine, QwenEngine):
            engine.on_progress = lambda stage: None


def run_worker(service: Service, once: bool = False) -> None:
    with FileLock(str(service.settings.data_dir / "worker.lock"), timeout=0):
        service.recover()
        stop = threading.Event()
        heartbeat = service.settings.data_dir / "worker.json"

        engine = QwenEngine(service.settings)

        def beat() -> None:
            while not stop.is_set():
                temp = heartbeat.with_suffix(".tmp")
                temp.write_text(
                    json.dumps(
                        {"updated": time.time(), "pid": os.getpid(), "inference_verified": engine.verified}
                    )
                )
                os.replace(temp, heartbeat)
                stop.wait(5)

        thread = threading.Thread(target=beat, daemon=True)
        thread.start()
        try:
            while True:
                job = service.claim()
                if job:
                    if hasattr(engine, "select"):
                        engine.select(job.get("engine", "qwen"))
                    process_job(service, engine, job)
                elif once:
                    break
                else:
                    time.sleep(1)
        finally:
            if hasattr(engine, "close"):
                engine.close()
            stop.set()
            thread.join()
            heartbeat.unlink(missing_ok=True)
