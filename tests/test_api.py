import threading
import time

import pytest
from fastapi.testclient import TestClient
from test_ownvoice import FakeEngine

from ownvoice import api
from ownvoice.app import create_app
from ownvoice.config import Settings
from ownvoice.repository import Repository
from ownvoice.worker import process_job


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "POLL_SECONDS", 0.01)
    app = create_app(Settings(data_dir=tmp_path))
    with app.state.service.uow() as work:
        Repository(work.session).add("profile", "test", {"name": "Test", "transcript": "hello"})
    with TestClient(app) as client:
        yield client


def payload(**kwargs):
    return {"model": "qwen", "voice": "test", "input": "Hello.", **kwargs}


def test_discovery_validation_and_origin(client):
    assert len(client.get("/v1/models").json()["data"]) == 3
    assert client.get("/v1/voices").json()["data"] == [{"id": "test", "name": "Test"}]
    for extra in (
        {"speed": 2},
        {"response_format": "mp3"},
        {"stream_format": "sse"},
        {"unexpected": True},
        {"input": "   "},
        {"model": "unknown"},
    ):
        assert client.post("/v1/audio/speech", json=payload(**extra)).status_code == 422
    assert client.post("/v1/jobs", json=payload(), headers={"Origin": "https://evil.test"}).status_code == 403
    assert client.post("/v1/jobs", content="{}", headers={"Content-Type": "text/plain"}).status_code == 403
    assert client.post("/v1/jobs", json=payload(voice="missing")).status_code == 404
    assert client.get("/v1/jobs/missing/events").status_code == 404
    assert client.app.state.service.list("job") == []


def test_async_srt_events_and_audio(client):
    created = client.post(
        "/v1/jobs", json=payload(mode="srt", input="1\n00:00:01,000 --> 00:00:02,000\nHello")
    )
    assert created.status_code == 202
    base = created.headers["location"]
    assert client.get(base + "/audio").status_code == 409
    service = client.app.state.service
    process_job(service, FakeEngine(), service.claim())
    job = client.get(base).json()
    assert job["status"] == "completed" and job["progress"]["percent"] == 100
    events = client.get(base + "/events")
    assert events.headers["content-type"].startswith("text/event-stream")
    assert "event: segment_ready" in events.text and "event: completed" in events.text
    assert client.get(job["audio_url"]).content[:4] == b"RIFF"
    assert client.get(job["segments"][0]["audio_url"]).status_code == 200
    # A reconnect receives current state and completed segments, not an empty stream.
    assert "event: completed" in client.get(base + "/events").text
    assert client.patch(base + "/segments/0", json={"text": "Changed"}).status_code == 202
    assert client.get(base + "/audio").status_code == 409


def test_review_and_failed_events(client):
    service = client.app.state.service
    response = client.post(
        "/v1/jobs", json=payload(mode="srt", input="1\n00:00:00,000 --> 00:00:00,100\nLong")
    )
    base = response.headers["location"]
    process_job(service, FakeEngine(seconds=2), service.claim())
    events = client.get(base + "/events").text
    assert "event: needs_review" in events and "event: segment_ready" not in events
    assert client.get(base + "/audio").status_code == 409
    assert client.post(base + "/retry", headers={"Content-Type": "application/json"}).status_code == 202
    job = service.claim()
    job.update(status="failed", error="Test failure")
    service.update_job(job["id"], job)
    assert "event: failed" in client.get(base + "/events").text


def test_speech_waits_for_worker(client):
    service = client.app.state.service
    failures = []

    def worker():
        try:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                job = service.claim()
                if job:
                    process_job(service, FakeEngine(), job)
                    return
                time.sleep(0.01)
            failures.append("No queued job")
        except Exception as exc:
            failures.append(exc)

    thread = threading.Thread(target=worker)
    thread.start()
    response = client.post("/v1/audio/speech", json=payload())
    thread.join(timeout=5)
    assert not failures and not thread.is_alive()
    assert response.status_code == 200 and response.content[:4] == b"RIFF"
    assert response.headers["content-type"] == "audio/wav"
    assert client.get(response.headers["location"]).json()["status"] == "completed"


def test_wait_timeout_preserves_job(client, monkeypatch):
    monkeypatch.setattr(api, "SPEECH_TIMEOUT", 0)
    response = client.post("/v1/audio/speech", json=payload())
    assert response.status_code == 504
    assert response.json()["error"]["code"] == "wait_timeout"
    assert client.get(response.headers["location"]).json()["status"] == "queued"


def test_sse_observes_live_worker_transition(client):
    service = client.app.state.service
    result = client.post("/v1/jobs", json=payload())
    base = result.headers["location"]

    def worker():
        time.sleep(0.1)
        process_job(service, FakeEngine(), service.claim())

    thread = threading.Thread(target=worker)
    thread.start()
    result = client.get(base + "/events")
    thread.join(timeout=5)
    assert "event: progress" in result.text
    assert "event: segment_ready" in result.text
    assert "event: completed" in result.text
