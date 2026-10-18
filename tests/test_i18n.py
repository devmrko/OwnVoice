import json
import re
from pathlib import Path

from fastapi.testclient import TestClient

from ownvoice.app import create_app
from ownvoice.config import Settings
from ownvoice.i18n import language, localize_job, translate


def test_catalog_keys_and_parameters_match():
    root = Path(__file__).parents[1] / "src/ownvoice/static/locales"
    ko = json.loads((root / "ko.json").read_text(encoding="utf-8"))
    en = json.loads((root / "en.json").read_text(encoding="utf-8"))
    assert ko.keys() == en.keys()
    for key in ko:
        assert sorted(re.findall(r"\{\d+\}", ko[key])) == sorted(re.findall(r"\{\d+\}", en[key]))
        assert en[key].strip()


def test_language_negotiation_and_saved_messages():
    assert language("en-US,en;q=0.9,ko;q=0.8") == "en"
    assert language("en;q=0,ko;q=0.5") == "ko"
    assert language("fr") == "ko"
    assert (
        translate("SRT 3번 시간 형식이 잘못되었습니다.", "en") == "Invalid timestamp format in SRT segment 3."
    )
    job = {
        "error": "시간을 초과한 구간을 수정하거나 다시 생성해 주세요.",
        "segments": [
            {
                "text": "완료",
                "original": "완료",
                "timing_error": "3회 시도 · 배정 1.00초 · 최단 음성 1.40초 · 최대 1.15배 가속으로 맞출 수 없습니다.",
            }
        ],
    }
    localized = localize_job(job, "en")
    assert localized["segments"][0]["text"] == "완료"
    assert "Allotted 1.00s" in localized["segments"][0]["timing_error"]
    assert job["error"].startswith("시간")  # Stored object remains unchanged.


def test_api_errors_follow_request_language(tmp_path):
    with TestClient(create_app(Settings(data_dir=tmp_path))) as client:
        for locale, expected in [("en-US", "Item not found."), ("ko", "항목을 찾을 수 없습니다.")]:
            response = client.get("/api/jobs/missing", headers={"Accept-Language": locale})
            assert response.status_code == 404
            assert response.json()["detail"] == expected
        response = client.post("/api/jobs", json={}, headers={"Accept-Language": "en", "X-OwnVoice": "1"})
        assert response.status_code == 422
        assert response.json()["detail"] == "Check the input."
        assert response.headers["content-language"] == "en"
        assert client.get("/static/locales/en.json").status_code == 200
