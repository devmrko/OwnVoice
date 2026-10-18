import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient
from python_foundation.errors import BusinessError

from ownvoice.app import create_app
from ownvoice.audio import RATE, TimingOverflow, fit_audio, write_atomic
from ownvoice.config import Settings
from ownvoice.domain import JobRequest, parse_segments
from ownvoice.service import Service
from ownvoice.worker import process_job


@pytest.fixture
def service(tmp_path):
    instance = Service(Settings(data_dir=tmp_path))
    with instance.uow() as work:
        from ownvoice.repository import Repository

        Repository(work.session).add("profile", "test", {"name": "Test", "transcript": "안녕하세요"})
    yield instance
    instance.engine.dispose()


class FakeEngine:
    def __init__(self, seconds=0.2):
        self.seconds = seconds
        self.calls = 0

    def synthesize(self, text, reference, transcript, language):
        self.calls += 1
        return np.full(round(RATE * self.seconds), 0.25, dtype=np.float32)


def test_srt_parser():
    s = parse_segments("srt", "\ufeff1\r\n00:00:05,123 --> 00:00:06,321\r\n안녕\r\n세계")
    assert s[0].start_ms == 5123
    assert s[0].end_ms == 6321
    assert s[0].text == "안녕 세계"


@pytest.mark.parametrize(
    "content",
    [
        "",
        "1\n00:00:01,000 --> 00:00:00,000\nBad",
        "1\n00:00:00,000 --> 00:00:02,000\nA\n\n2\n00:00:01,000 --> 00:00:03,000\nB",
        "1\n00:60:00,000 --> 00:61:00,000\nA",
    ],
)
def test_bad_subtitles(content):
    with pytest.raises(BusinessError):
        parse_segments("srt", content)


def test_exact_timeline_and_cache(service):
    request = JobRequest(
        profile_id="test",
        mode="srt",
        content="1\n00:00:01,123 --> 00:00:02,000\nHello\n\n2\n00:00:03,000 --> 00:00:04,000\nWorld",
    )
    job = service.create_job(request)
    engine = FakeEngine()
    process_job(service, engine, service.claim())
    done = service.get("job", job["id"])
    assert done["status"] == "completed"
    data, rate = sf.read(service.audio_path(job["id"]))
    assert rate == RATE and len(data) == RATE * 4
    start = round(1.123 * RATE)
    assert np.all(data[:start] == 0)
    assert data[start] > 0.2
    assert np.all(data[start + round(0.2 * RATE) : RATE * 3] == 0)
    service.edit(job["id"], 0, "Updated")
    with pytest.raises(BusinessError):
        service.audio_path(job["id"])
    process_job(service, engine, service.claim())
    assert engine.calls == 3  # Only edited segment regenerated.


def test_overflow_does_not_export(service):
    job = service.create_job(
        JobRequest(profile_id="test", mode="srt", content="1\n00:00:00,000 --> 00:00:01,000\nLong")
    )
    process_job(service, FakeEngine(seconds=2), service.claim())
    saved = service.get("job", job["id"])
    assert saved["status"] == "needs_review"
    assert saved["segments"][0]["status"] == "needs_review"
    with pytest.raises(BusinessError):
        service.audio_path(job["id"])
    assert not (service.settings.data_dir / "jobs" / job["id"] / "output.wav").exists()


def test_recover_and_failure(service):
    job = service.create_job(JobRequest(profile_id="test", mode="text", content="Hi"))
    service.claim()
    service.recover()
    assert service.get("job", job["id"])["status"] == "queued"

    class Broken:
        def synthesize(self, *args):
            raise RuntimeError("private provider detail")

    process_job(service, Broken(), service.claim())
    saved = service.get("job", job["id"])
    assert saved["status"] == "failed"
    assert "private" not in saved["error"]
    service.edit(job["id"])
    process_job(service, FakeEngine(), service.claim())
    assert service.get("job", job["id"])["status"] == "completed"


def test_speed_limit(tmp_path):
    raw = tmp_path / "raw.wav"
    wave = np.sin(np.arange(round(RATE * 1.08)) * 2 * np.pi * 200 / RATE).astype(np.float32)
    write_atomic(raw, wave)
    data, speed = fit_audio(raw, RATE, 1.15)
    assert len(data) <= RATE
    assert 1 < speed <= 1.15
    with pytest.raises(TimingOverflow):
        fit_audio(raw, RATE // 2, 1.15)


def test_api_boundaries(tmp_path):
    app = create_app(Settings(data_dir=tmp_path))
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        assert client.get("/static/app.js").status_code == 200
        assert client.post("/api/jobs", json={}).status_code == 403
        assert (
            client.post(
                "/api/jobs", headers={"X-OwnVoice": "1", "Origin": "https://evil.example"}, json={}
            ).status_code
            == 403
        )
        assert client.get("/api/profiles", headers={"Host": "evil.example"}).status_code in (400, 403)
        assert (
            client.post(
                "/api/jobs",
                headers={"X-OwnVoice": "1"},
                json={"profile_id": "missing", "mode": "text", "content": "hello"},
            ).status_code
            == 404
        )
        assert client.get("/api/jobs/unknown/audio").status_code == 404
        assert (
            client.post(
                "/api/profiles",
                headers={"X-OwnVoice": "1"},
                data={"name": "bad"},
                files={"audio": ("bad.wav", b"not audio")},
            ).status_code
            == 400
        )
        assert client.get("/api/profiles").json() == []


def test_real_upload_and_text_job(tmp_path):
    path = tmp_path / "reference.wav"
    write_atomic(path, np.sin(np.arange(RATE * 3) * 2 * np.pi * 220 / RATE).astype(np.float32))
    app = create_app(Settings(data_dir=tmp_path / "app"))
    headers = {"X-OwnVoice": "1"}
    with TestClient(app) as client:
        response = client.post(
            "/api/profiles",
            headers=headers,
            data={"name": "My voice", "transcript": "hello"},
            files={"audio": ("voice.wav", path.read_bytes())},
        )
        assert response.status_code == 201
        profile_id = response.json()["id"]
        result = client.post(
            "/api/jobs",
            headers=headers,
            json={"profile_id": profile_id, "mode": "text", "content": "Hello. World."},
        )
        assert result.status_code == 201
        key = result.json()["id"]
        service = app.state.service
        assert (
            client.patch(f"/api/jobs/{key}/segments/0", headers=headers, json={"text": "Edit"}).status_code
            == 409
        )
        process_job(service, FakeEngine(), service.claim())
        wav = client.get(f"/api/jobs/{key}/audio")
        assert wav.status_code == 200
        assert wav.content[:4] == b"RIFF"
        assert (
            client.patch(f"/api/jobs/{key}/segments/0", headers=headers, json={"text": "   "}).status_code
            == 422
        )


def test_device_order(monkeypatch):
    import sys
    from types import SimpleNamespace

    from ownvoice.engine import detect_device

    torch = SimpleNamespace(
        cuda=SimpleNamespace(is_available=lambda: True),
        backends=SimpleNamespace(mps=SimpleNamespace(is_available=lambda: True)),
    )
    monkeypatch.setitem(sys.modules, "torch", torch)
    assert detect_device() == "cuda:0"
    torch.cuda.is_available = lambda: False
    assert detect_device() == "mps"
    torch.backends.mps.is_available = lambda: False
    assert detect_device() == "cpu"
    with pytest.raises(ValueError):
        detect_device("cuda")


def test_cuda_detection_without_mps_backend(monkeypatch):
    import sys
    from types import SimpleNamespace

    from ownvoice.engine import detect_device

    torch = SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: True), backends=SimpleNamespace())
    monkeypatch.setitem(sys.modules, "torch", torch)
    assert detect_device() == "cuda:0"
