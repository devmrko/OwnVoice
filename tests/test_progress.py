from test_ownvoice import FakeEngine, service  # noqa: F401

from ownvoice.domain import JobRequest
from ownvoice.progress import job_progress
from ownvoice.worker import process_job


def job(status="running"):
    return {
        "status": status,
        "created_at": "2026-01-01T00:00:00+00:00",
        "started_at": 100.0,
        "stage": "synthesizing",
        "stage_started_at": 120.0,
        "segments": [
            {"status": "completed", "text": "aaaa"},
            {"status": "completed", "text": "bbbb"},
            {"status": "pending", "text": "abcdefgh"},
        ],
        "synthesis_timings": [{"seconds": 4.0, "chars": 4}, {"seconds": 4.0, "chars": 4}],
    }


def test_running_estimates_from_measured_samples():
    p = job_progress(job(), now=122.0)
    assert p["elapsed_seconds"] == 22
    assert p["eta_seconds"] == 6
    assert p["percent"] == 67
    assert p["done"] == 2


def test_no_estimate_during_preparation_or_without_samples():
    data = job()
    data["stage"] = "model_loading"
    assert job_progress(data, now=122.0)["eta_seconds"] is None
    data["stage"] = "synthesizing"
    data["synthesis_timings"] = []
    assert job_progress(data, now=122.0)["eta_seconds"] is None


def test_no_fabricated_eta_when_measurement_is_insufficient_or_exceeded():
    data = job()
    data["synthesis_timings"] = data["synthesis_timings"][:1]
    assert job_progress(data, now=122.0)["eta_seconds"] is None
    assert job_progress(job(), now=140.0)["eta_seconds"] is None


def test_completion_frozen_and_legacy_unknown():
    data = job("completed")
    data["finished_at"] = 130.0
    assert job_progress(data, now=900.0)["elapsed_seconds"] == 30
    assert job_progress(data, now=900.0)["eta_seconds"] is None
    del data["started_at"]
    assert job_progress(data, now=900.0)["elapsed_seconds"] is None


def test_review_not_false_completion():
    data = job("needs_review")
    data["segments"][-1]["status"] = "needs_review"
    p = job_progress(data, now=130.0)
    assert p["percent"] == 67 and p["needs_review"] == 1


def test_worker_timestamps_and_retry_reset(service):  # noqa: F811
    original = service.create_job(JobRequest(profile_id="test", mode="text", content="One. Two."))
    process_job(service, FakeEngine(), service.claim())
    saved = service.get("job", original["id"])
    assert saved["stage"] == "completed"
    assert saved["finished_at"] >= saved["started_at"]
    assert saved["progress"]["percent"] == 100
    assert len(saved["synthesis_timings"]) == 2
    elapsed = saved["progress"]["elapsed_seconds"]
    assert service.get("job", original["id"])["progress"]["elapsed_seconds"] == elapsed
    retried = service.edit(original["id"], 0, "New")
    assert retried["started_at"] is None and retried["finished_at"] is None
    assert retried["synthesis_timings"] == []
    assert retried["progress"]["percent"] == 50
