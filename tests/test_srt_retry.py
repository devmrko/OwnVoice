import numpy as np
import soundfile as sf
from test_ownvoice import service  # noqa: F401

from ownvoice.audio import RATE
from ownvoice.domain import JobRequest
from ownvoice.worker import process_job


class SequenceEngine:
    def __init__(self, durations):
        self.durations = iter(durations)
        self.calls = []

    def synthesize(self, text, *args):
        self.calls.append(text)
        return np.full(round(next(self.durations) * RATE), 0.25, dtype=np.float32)


def test_retry_fits_multiple_srt_cues_and_exports_exact_timeline(service):  # noqa: F811
    job = service.create_job(
        JobRequest(
            profile_id="test",
            mode="srt",
            content=(
                "1\n00:00:00,500 --> 00:00:01,800\nFirst\n\n"
                "2\n00:00:02,000 --> 00:00:03,000\nSecond\n\n"
                "3\n00:00:04,000 --> 00:00:05,000\nThird"
            ),
        )
    )
    engine = SequenceEngine([1.6, 1.2, 0.5, 1.5, 1.4, 0.8])
    process_job(service, engine, service.claim())
    saved = service.get("job", job["id"])
    assert saved["status"] == "completed"
    assert [s["synthesis_attempts"] for s in saved["segments"]] == [2, 1, 3]
    assert engine.calls == ["First", "First", "Second", "Third", "Third", "Third"]
    audio, rate = sf.read(service.audio_path(job["id"]))
    assert rate == RATE and len(audio) == 5 * RATE
    assert np.all(audio[: RATE // 2] == 0)
    assert audio[2 * RATE] > 0.2 and audio[4 * RATE] > 0.2
    assert len(saved["synthesis_timings"]) == 6


def test_exhaustion_is_bounded_preserves_shortest_and_continues(service):  # noqa: F811
    job = service.create_job(
        JobRequest(
            profile_id="test",
            mode="srt",
            content=("1\n00:00:00,000 --> 00:00:01,000\nLong\n\n2\n00:00:02,000 --> 00:00:03,000\nFits"),
        )
    )
    engine = SequenceEngine([1.6, 1.4, 1.8, 0.5])
    process_job(service, engine, service.claim())
    saved = service.get("job", job["id"])
    assert saved["status"] == "needs_review"
    first, second = saved["segments"]
    assert first["synthesis_attempts"] == 3
    assert first["duration_ms"] == 1400
    assert "배정 1.00초" in first["timing_error"]
    assert second["status"] == "completed"
    assert sf.info(service.audio_path(job["id"], 0)).frames == round(1.4 * RATE)
    assert not (service.settings.data_dir / "jobs" / job["id"] / "output.wav").exists()
    # Manual retry starts a new attempt budget, preserving already completed cues.
    service.edit(job["id"])
    retry = SequenceEngine([0.9])
    process_job(service, retry, service.claim())
    assert retry.calls == ["Long"]
    assert service.get("job", job["id"])["status"] == "completed"


def test_text_is_not_retried_and_retry_can_be_disabled(service):  # noqa: F811
    job = service.create_job(JobRequest(profile_id="test", mode="text", content="Long"))
    engine = SequenceEngine([2.0])
    process_job(service, engine, service.claim())
    assert service.get("job", job["id"])["status"] == "completed"
    service.settings.srt_max_attempts = 1
    job = service.create_job(
        JobRequest(profile_id="test", mode="srt", content="1\n00:00:00,000 --> 00:00:01,000\nLong")
    )
    engine = SequenceEngine([2.0])
    process_job(service, engine, service.claim())
    assert len(engine.calls) == 1
    assert service.get("job", job["id"])["status"] == "needs_review"
