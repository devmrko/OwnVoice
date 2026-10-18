"""Build a private listening report from existing jobs; never runs synthesis."""

import argparse
import html
import json
import shutil
from pathlib import Path

from ownvoice.config import Settings
from ownvoice.service import Service


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("jobs", type=Path, help="JSON mapping engine IDs to existing job IDs")
    parser.add_argument("output", type=Path, help="Private comparison output directory")
    args = parser.parse_args()
    service = Service(Settings())
    jobs = {engine: service.get("job", key) for engine, key in json.loads(args.jobs.read_text()).items()}
    if not jobs or any(job["status"] != "completed" for job in jobs.values()):
        raise SystemExit("Wait until all comparison jobs have completed.")
    first = next(iter(jobs.values()))
    texts = [s["text"] for s in first["segments"]]
    if any(
        j["profile_id"] != first["profile_id"] or [s["text"] for s in j["segments"]] != texts
        for j in jobs.values()
    ):
        raise SystemExit("Comparison requires identical reference voice and sentence text.")
    args.output.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(
        service.settings.data_dir / "profiles" / first["profile_id"] / "reference.wav",
        args.output / "reference-with.wav",
    )
    rows = []
    for job in jobs.values():
        perf = job["progress"]["performance"]
        loading = job["phase_seconds"].get("model_loading")
        loading_label = f"{loading:.1f} s" if loading is not None else "캐시 사용"
        rows.append(
            f"<tr><th>{html.escape(job['engine_name'])}</th>"
            f"<td>{perf['synthesis_seconds']:.1f} s</td>"
            f"<td>{perf['audio_seconds']:.2f} s</td>"
            f"<td>{perf['rtf']:.2f}</td>"
            f"<td>{loading_label}</td></tr>"
        )
    cards = []
    for index, text in enumerate(texts):
        players = []
        for engine, job in jobs.items():
            filename = f"{engine}-{index + 1}.wav"
            shutil.copyfile(service.audio_path(job["id"], index), args.output / filename)
            seconds = sum(t["seconds"] for t in job["synthesis_timings"] if t["segment_index"] == index)
            players.append(
                f"<div><b>{html.escape(job['engine_name'])}</b>"
                f'<audio controls preload="none" src="{filename}"></audio>'
                f"<small><span>합성</span> {seconds:.1f} s · <span>음성</span> {job['segments'][index]['duration_ms'] / 1000:.2f} s</small></div>"
            )
        cards.append(
            f'<section><p>{html.escape(text)}</p><div class="players">{"".join(players)}</div></section>'
        )
    (args.output / "measurements.json").write_text(
        json.dumps(jobs, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (args.output / "index.html").write_text(
        '<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
        "<title>OwnVoice 모델 비교</title><style>body{font:16px system-ui;background:#f5f4f1;color:#302d29;"
        "max-width:1200px;margin:32px auto;padding:0 20px}section{background:white;border:1px solid #ddd;"
        "padding:20px;margin:20px 0}audio{display:block;width:100%;margin:12px 0}.players{display:grid;"
        "grid-template-columns:repeat(3,minmax(0,1fr));gap:20px}table{border-collapse:collapse;width:100%}"
        "td,th{text-align:left;padding:12px;border-bottom:1px solid #ddd}.table{overflow:auto}"
        "@media(max-width:720px){.players{grid-template-columns:1fr}}small{color:#625d55}</style>"
        '<a href="/">OwnVoice</a><select id="ui-locale" aria-label="화면 언어"><option value="ko">한국어</option><option value="en">English</option></select><h1>모델 비교</h1>'
        "<p>같은 참조 녹음 · 같은 문장. Qwen은 대본 사용, Chatterbox는 음성만 사용합니다.</p>"
        "<p>각 모델 1회 실행 결과입니다. 무작위 생성에 따른 차이가 있으며 일반 성능을 보장하지 않습니다.</p>"
        '<section><b>참조 녹음</b><audio controls src="reference-with.wav"></audio></section>'
        '<div class="table"><table><tr><th>모델</th><th>합성 합계</th><th>생성 음성</th><th>RTF</th><th>모델 로딩</th></tr>'
        + "".join(rows)
        + "</table></div><p>RTF = 합성 시간 ÷ 음성 길이. 낮을수록 빠릅니다. 다운로드·로딩·구간 사이 무음은 합성 합계에서 제외합니다.</p>"
        + "".join(cards)
        + "<p>목소리 유사도와 자연스러움을 직접 듣고, 음성 생성 화면에서 모델을 선택하세요.</p>"
        + '<script src="/static/i18n.js"></script><script>OwnVoiceI18n.ready.then(()=>{document.getElementById("ui-locale").onchange=e=>OwnVoiceI18n.setLocale(e.target.value);});</script></html>',
        encoding="utf-8",
    )
    service.engine.dispose()
    print(args.output / "index.html")


if __name__ == "__main__":
    main()
