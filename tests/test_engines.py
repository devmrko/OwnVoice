import pytest
from pydantic import ValidationError
from test_ownvoice import service  # noqa: F401

from ownvoice.domain import JobRequest
from ownvoice.engine import QwenEngine
from ownvoice.engine_catalog import SMALL_MODEL


def test_engine_selection_persists_and_legacy_defaults(service):  # noqa: F811
    job = service.create_job(JobRequest(profile_id="test", mode="text", content="Hello", engine="qwen-small"))
    assert job["engine"] == "qwen-small"
    assert job["model"] == SMALL_MODEL
    assert JobRequest(profile_id="test", mode="text", content="Hi").engine == "qwen"
    with pytest.raises(ValidationError):
        JobRequest(profile_id="test", mode="text", content="Hi", engine="unknown")


def test_chatterbox_python_preserves_venv_symlink(monkeypatch, tmp_path):
    import os

    from ownvoice.engine_catalog import chatterbox_python

    if os.name == "nt":
        pytest.skip("Windows venv uses an executable, not a symlink")
    base = tmp_path / "base-python"
    base.touch()
    venv = tmp_path / "venv-python"
    venv.symlink_to(base)
    monkeypatch.setenv("OWNVOICE_CHATTERBOX_PYTHON", str(venv))
    assert chatterbox_python() == venv


def test_switch_unloads_model_before_next_engine(service, monkeypatch):  # noqa: F811
    engine = QwenEngine(service.settings)
    released = []
    monkeypatch.setattr(engine, "close", lambda: released.append(engine.selected))
    engine.select("qwen-small")
    assert engine.active_model == SMALL_MODEL
    engine.select("qwen-small")
    engine.select("chatterbox")
    engine.select("qwen")
    assert released == ["qwen", "qwen-small", "chatterbox"]
    assert engine.active_model == service.settings.model


def test_chatterbox_requires_install_and_explicit_language(service, monkeypatch, tmp_path):  # noqa: F811
    from python_foundation.errors import BusinessError

    from ownvoice import engine_catalog

    python = tmp_path / "python"
    monkeypatch.setattr(engine_catalog, "chatterbox_python", lambda: python)
    request = JobRequest(profile_id="test", mode="text", content="Hello", engine="chatterbox")
    with pytest.raises(BusinessError):
        service.create_job(request)
    python.touch()
    request.language = "Auto"
    with pytest.raises(BusinessError):
        service.create_job(request)
    request.language = "Korean"
    assert service.create_job(request)["engine"] == "chatterbox"
