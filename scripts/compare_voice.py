"""Local listening experiment; never modifies registered profiles or jobs.

Run with the TTS environment: python scripts/compare_voice.py PROFILE_ID
Outputs private WAVs, measured timings and a listening page under .data/diagnostics.
Stop the application worker first; the experiment holds its lock to avoid two GPU models.
"""

import argparse
import html
import json
import random
import shutil
import time
from datetime import datetime

import numpy as np
import soundfile as sf
from filelock import FileLock, Timeout

from ownvoice.audio import RATE, write_atomic
from ownvoice.config import Settings
from ownvoice.engine import QwenEngine, detect_device
from ownvoice.service import Service

TEXTS = [
    "오늘은 제 목소리로 새로운 소식을 전해 드리겠습니다.",
    "에이아이 에이전트의 데이터 조회도 사용자 권한에 맞게 통제하는 방법입니다.",
    "설정이 끝났나요? 이제 결과를 확인하고, 필요한 부분을 수정해 주세요.",
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile_id")
    args = parser.parse_args()
    settings = Settings()
    service = Service(settings)
    profile = service.get("profile", args.profile_id)
    if not profile["transcript"]:
        parser.error("A verified reference transcript is required for this comparison.")
    if any(j["status"] in ("queued", "running") for j in service.list("job")):
        parser.error("Wait for existing jobs to finish before running the comparison.")
    folder = settings.data_dir / "diagnostics" / datetime.now().strftime("voice-comparison-%Y%m%d-%H%M%S")
    folder.mkdir(parents=True)
    source = settings.data_dir / "profiles" / args.profile_id / "reference.wav"
    # Distinct paths keep QwenEngine's reference prompt cache separate by condition.
    for name in ("without", "with"):
        shutil.copyfile(source, folder / f"reference-{name}.wav")
    samples, rate = sf.read(source)
    result = {
        "model": settings.model,
        "device": detect_device(settings.device),
        "reference_seconds": len(samples) / rate,
        "reference_peak": float(np.max(np.abs(samples))),
        "reference_transcript": profile["transcript"],
        "started_at": datetime.now().isoformat(),
        "status": "running",
        "samples": [],
    }
    engine = QwenEngine(settings)
    started = time.perf_counter()

    def save() -> None:
        result["elapsed_seconds"] = round(time.perf_counter() - started, 3)
        (folder / "measurements.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    print(f"OUTPUT {folder.resolve()}", flush=True)
    save()
    try:
        import torch

        for index, text in enumerate(TEXTS):
            for mode in ("without", "with") if index % 2 == 0 else ("with", "without"):
                seed = 20261018 + index
                random.seed(seed)
                np.random.seed(seed)
                torch.manual_seed(seed)
                phases: dict[str, float] = {}
                last_stage = "initializing"
                last_time = time.perf_counter()

                def progress(
                    stage: str, phases: dict[str, float] = phases, mode: str = mode, seed: int = seed
                ) -> None:
                    nonlocal last_stage, last_time
                    now = time.perf_counter()
                    phases[last_stage] = phases.get(last_stage, 0) + now - last_time
                    last_stage, last_time = stage, now
                    if stage == "synthesizing":
                        random.seed(seed)
                        np.random.seed(seed)
                        torch.manual_seed(seed)
                    print(f"{len(result['samples']) + 1}/6 {mode} {stage}", flush=True)

                engine.on_progress = progress
                before = time.perf_counter()
                wave = engine.synthesize(
                    text,
                    folder / f"reference-{mode}.wav",
                    profile["transcript"] if mode == "with" else "",
                    "Korean",
                )
                # Synchronize before recording completion of asynchronous GPU work.
                if result["device"] == "mps":
                    torch.mps.synchronize()
                elif result["device"].startswith("cuda"):
                    torch.cuda.synchronize()
                end = time.perf_counter()
                phases[last_stage] = phases.get(last_stage, 0) + end - last_time
                filename = f"{index + 1}-{mode}.wav"
                write_atomic(folder / filename, wave)
                record = {
                    "text": text,
                    "mode": mode,
                    "file": filename,
                    "seed": seed,
                    "audio_seconds": round(len(wave) / RATE, 3),
                    "wall_seconds": round(end - before, 3),
                    "phase_seconds": {k: round(v, 3) for k, v in phases.items()},
                }
                result["samples"].append(record)
                save()
                print(json.dumps(record, ensure_ascii=False), flush=True)
        result["status"] = "completed"
    except BaseException as exc:
        result["status"] = "failed"
        result["error"] = str(exc)
        raise
    finally:
        save()
        cards = []
        for text in TEXTS:
            players = []
            for mode, label in (("without", "대본 없음"), ("with", "대본 사용 · 현재 방식")):
                row = next((r for r in result["samples"] if r["text"] == text and r["mode"] == mode), None)
                if row:
                    synth = row["phase_seconds"].get("synthesizing", 0)
                    players.append(
                        f'<div><b>{label}</b><audio controls preload="none" src="{row["file"]}"></audio>'
                        f"<small>합성 {synth:.1f}초 · 준비 포함 {row['wall_seconds']:.1f}초"
                        f" · 음성 {row['audio_seconds']:.2f}초</small></div>"
                    )
            cards.append(
                f'<section><p>{html.escape(text)}</p><div class="pair">{"".join(players)}</div></section>'
            )
        (folder / "index.html").write_text(
            '<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
            "<title>OwnVoice 음성 비교</title><style>body{font:16px system-ui;background:#f5f4f1;color:#302d29;"
            "max-width:1000px;margin:32px auto;padding:0 20px}section{background:white;padding:20px;margin:16px 0;"
            "border:1px solid #ddd;border-radius:4px}.pair{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));"
            "gap:24px}audio{display:block;width:100%;margin:12px 0}small{color:#625d55}"
            "@media(max-width:600px){.pair{grid-template-columns:1fr}}</style>"
            "<h1>음성 비교</h1><p>동일 녹음 · 동일 문장 · 문장별 동일 시드. 모델 실행에 따른 변동은 있을 수 있습니다.</p>"
            "<p>목소리 유사도, 발음, 문장 누락을 듣고 비교하세요. 자동 품질 점수는 제공하지 않습니다.</p>"
            '<section><b>참조 녹음</b><audio controls src="reference-with.wav"></audio>'
            f"<p>{html.escape(profile['transcript'])}</p></section>"
            + "".join(cards)
            + "<p>첫 합성은 모델 로딩을 포함합니다. 원본 WAV이며 속도·음량 보정은 적용하지 않았습니다.</p></html>",
            encoding="utf-8",
        )


if __name__ == "__main__":
    settings = Settings()
    settings.prepare()
    try:
        with FileLock(str(settings.data_dir / "worker.lock"), timeout=0):
            main()
    except Timeout:
        raise SystemExit("Stop the OwnVoice worker before running a standalone GPU comparison.") from None
