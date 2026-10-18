import os
import signal
import subprocess
import sys
import time

import pytest
from filelock import FileLock
from test_ownvoice import FakeEngine, service  # noqa: F401

from ownvoice.cli import download_model
from ownvoice.config import Settings
from ownvoice.domain import JobRequest
from ownvoice.worker import process_job


def test_model_download_includes_tokenizer_and_offline(monkeypatch, tmp_path):
    from types import SimpleNamespace

    calls = []

    def snapshot(repo, **kwargs):
        calls.append((repo, kwargs))
        return str(tmp_path)

    monkeypatch.setitem(sys.modules, "huggingface_hub", SimpleNamespace(snapshot_download=snapshot))
    with pytest.raises(ValueError):
        download_model(Settings(), offline=True)
    (tmp_path / "speech_tokenizer").mkdir()
    for filename in (
        "config.json",
        "generation_config.json",
        "speech_tokenizer/config.json",
        "model.safetensors",
        "speech_tokenizer/model.safetensors",
    ):
        (tmp_path / filename).write_text("test fixture")
    assert download_model(Settings(), offline=True) == tmp_path
    assert calls[-1][1] == {"local_files_only": True}


def test_second_worker_refuses_lock_and_leaves_jobs_untouched(service):  # noqa: F811
    job = service.create_job(JobRequest(profile_id="test", mode="text", content="Hello"))
    service.claim()
    env = {**os.environ, "PYTHONUTF8": "1", "OWNVOICE_DATA_DIR": str(service.settings.data_dir)}
    with FileLock(str(service.settings.data_dir / "worker.lock")):
        result = subprocess.run(
            [sys.executable, "-m", "ownvoice.cli", "worker", "--once"],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=20,
        )
    assert result.returncode != 0
    assert "이미 실행" in result.stderr
    assert service.get("job", job["id"])["status"] == "running"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signal recovery")
def test_interrupted_worker_recovers_completed_segments(service, tmp_path):  # noqa: F811
    job = service.create_job(JobRequest(profile_id="test", mode="text", content="First. Second."))
    marker = tmp_path / "in_second_segment"
    script = """
import signal, time
import numpy as np
from pathlib import Path
from ownvoice.config import Settings
from ownvoice.service import Service
import ownvoice.worker as w
from ownvoice.cli import interrupted
signal.signal(signal.SIGTERM, interrupted)
class Engine:
    verified = False
    def __init__(self, settings): self.calls = 0
    def synthesize(self, *args):
        self.on_progress("synthesizing")
        self.calls += 1
        if self.calls == 2:
            Path(MARKER).touch()
            time.sleep(60)
        return np.full(4800, 0.25, dtype=np.float32)
w.QwenEngine = Engine
w.detect_device = lambda _: "cpu"
w.run_worker(Service(Settings()), once=True)
""".replace("MARKER", repr(str(marker)))
    child = subprocess.Popen(
        [sys.executable, "-c", script],
        env={**os.environ, "OWNVOICE_DATA_DIR": str(service.settings.data_dir)},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 20
        while not marker.exists() and time.monotonic() < deadline and child.poll() is None:
            time.sleep(0.05)
        assert marker.exists()
        child.send_signal(signal.SIGTERM)
        child.wait(timeout=10)
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()
    assert not (tmp_path / "worker.json").exists()
    assert service.get("job", job["id"])["segments"][0]["status"] == "completed"
    service.recover()
    engine = FakeEngine()
    process_job(service, engine, service.claim())
    assert engine.calls == 1
    assert service.get("job", job["id"])["status"] == "completed"
