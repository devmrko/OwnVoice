from types import SimpleNamespace

from ownvoice.telemetry import device_details, performance


def test_rtf_uses_speech_not_timeline():
    job = {
        "synthesis_timings": [{"seconds": 20, "audio_seconds": 5, "chars": 10}],
        "segments": [{"duration_ms": 5000, "start_ms": 0, "end_ms": 60000}],
    }
    result = performance(job)
    assert result["rtf"] == 4
    assert "seconds_per_audio_minute" not in result
    assert result["first_segment_seconds"] == 20
    assert result["first_audio_ready_seconds"] is None


def test_legacy_unmatched_audio_not_guessed():
    result = performance(
        {"synthesis_timings": [{"seconds": 20}], "segments": [{"duration_ms": 5000}, {"duration_ms": 6000}]}
    )
    assert result["rtf"] is None
    assert result["first_segment_seconds"] == 20


def test_cuda_name_and_vram(monkeypatch):
    import sys

    device_details.cache_clear()
    monkeypatch.setitem(
        sys.modules,
        "torch",
        SimpleNamespace(
            cuda=SimpleNamespace(
                get_device_properties=lambda device: SimpleNamespace(
                    name="NVIDIA test GPU", total_memory=24 * 1024**3
                )
            )
        ),
    )
    result = device_details("cuda:0")
    assert result["name"] == "NVIDIA test GPU"
    assert result["memory_gb"] == 24
    assert result["memory_kind"] == "VRAM"
    device_details.cache_clear()


def test_apple_memory_labeled_shared(monkeypatch):
    device_details.cache_clear()
    monkeypatch.setattr("ownvoice.telemetry.platform.system", lambda: "Darwin")
    monkeypatch.setattr(
        "ownvoice.telemetry.subprocess.check_output",
        lambda args, **kwargs: "Apple M4" if "machdep.cpu.brand_string" in args else str(32 * 1024**3),
    )
    result = device_details("mps")
    assert result["name"] == "Apple M4"
    assert result["memory_gb"] == 32
    assert "공유" in result["memory_kind"]
    device_details.cache_clear()
