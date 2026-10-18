import time
from datetime import datetime
from typing import Any

from ownvoice.telemetry import performance


def job_progress(job: dict[str, Any], now: float | None = None) -> dict[str, Any]:
    now = time.time() if now is None else now
    segments = job["segments"]
    total = len(segments)
    done = sum(s["status"] == "completed" for s in segments)
    reviewed = sum(s["status"] == "needs_review" for s in segments)
    started = job.get("started_at")
    finished = job.get("finished_at")
    elapsed = max(0.0, (finished or now) - started) if started else None
    created = job.get("created_at")
    request_age = (
        max(0.0, now - datetime.fromisoformat(created).timestamp())
        if created and job["status"] in ("queued", "running")
        else None
    )
    # Use only this execution's measured samples, never a hardware-based default.
    timings = [t for t in job.get("synthesis_timings", []) if t["seconds"] > 0 and t["chars"] > 0]
    eta = None
    if job["status"] == "running" and job.get("stage") == "synthesizing" and len(timings) >= 2:
        seconds_per_char = sum(t["seconds"] for t in timings) / sum(t["chars"] for t in timings)
        remaining_chars = sum(len(s["text"]) for s in segments if s["status"] == "pending")
        current_elapsed = max(0.0, now - job.get("stage_started_at", now))
        prediction = remaining_chars * seconds_per_char - current_elapsed
        if prediction >= 1:
            eta = round(prediction)
    return {
        "stage": job.get("stage", "legacy_running" if job["status"] == "running" else job["status"]),
        "stage_started_at": job.get("stage_started_at"),
        "performance": performance(job),
        "current_attempt": job.get("current_attempt"),
        "attempt_limit": job.get("attempt_limit"),
        "current_segment": job.get("current_segment"),
        "total": total,
        "done": done,
        "needs_review": reviewed,
        "percent": (100 if done == total else min(99, round(done * 100 / total))) if total else 0,
        "elapsed_seconds": elapsed,
        "request_age_seconds": request_age,
        "eta_seconds": eta,
        "started_at": started,
        "finished_at": finished,
        "measured_at": now,
    }
