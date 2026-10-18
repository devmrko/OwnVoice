import argparse
import json
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import uvicorn
from filelock import Timeout

from ownvoice.config import Settings
from ownvoice.engine import runtime
from ownvoice.service import Service
from ownvoice.worker import run_worker


def doctor(settings: Settings) -> bool:
    state = runtime(settings)
    state["ffmpeg"] = shutil.which("ffmpeg")
    state["data_dir"] = str(settings.data_dir.resolve())
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return bool(state["tts_installed"] and state["ffmpeg"] and not state["error"])


def download_model(settings: Settings, offline: bool = False) -> Path:
    from huggingface_hub import snapshot_download

    local = Path(settings.model)
    if local.is_dir():
        path = local.resolve()
    else:
        path = Path(snapshot_download(settings.model, local_files_only=offline))
    required = ["config.json", "generation_config.json", "speech_tokenizer/config.json"]
    if any(not (path / name).is_file() for name in required):
        raise ValueError("모델 설정 또는 speech_tokenizer 파일이 없습니다. Base 모델을 확인하세요.")
    for folder in (path, path / "speech_tokenizer"):
        if not list(folder.glob("*.safetensors")):
            raise ValueError("모델 가중치가 없습니다. 다운로드를 다시 실행하세요.")
    print(f"모델 준비 완료: {path}")
    return path


def interrupted(signum: int, frame: Any) -> None:
    raise KeyboardInterrupt


def start(port: int) -> int:
    # Refuse an occupied port before starting a worker or touching job state.
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind(("127.0.0.1", port))
    processes: list[subprocess.Popen[bytes]] = []
    try:
        for command in (["web", "--port", str(port)], ["worker"]):
            processes.append(subprocess.Popen([sys.executable, "-m", "ownvoice.cli", *command]))
        print(f"OwnVoice: http://127.0.0.1:{port} · 종료: Ctrl+C", flush=True)
        while all(p.poll() is None for p in processes):
            time.sleep(0.5)
        return next((p.returncode for p in processes if p.returncode is not None), 1)
    except KeyboardInterrupt:
        return 0
    finally:
        for p in processes:
            if p.poll() is None:
                p.terminate()
        for p in processes:
            try:
                p.wait(timeout=15)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()


def main() -> None:
    parser = argparse.ArgumentParser(prog="ownvoice")
    parser.add_argument("command", choices=["start", "web", "worker", "doctor", "download-model"])
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--once", action="store_true", help="worker: process queued jobs then exit")
    parser.add_argument("--offline", action="store_true", help="download-model: verify cached files only")
    args = parser.parse_args()
    settings = Settings()
    signal.signal(signal.SIGTERM, interrupted)
    try:
        if args.command == "doctor":
            raise SystemExit(0 if doctor(settings) else 1)
        if args.command == "download-model":
            download_model(settings, args.offline)
        elif args.command == "start":
            if not doctor(settings):
                raise SystemExit("FFmpeg와 TTS 의존성을 설치한 뒤 다시 실행하세요.")
            raise SystemExit(start(args.port))
        elif args.command == "web":
            uvicorn.run("ownvoice.app:create_app", factory=True, host="127.0.0.1", port=args.port)
        else:
            service = Service(settings)
            try:
                run_worker(service, once=args.once)
            finally:
                service.engine.dispose()
    except KeyboardInterrupt:
        pass
    except Timeout:
        raise SystemExit("같은 데이터 경로의 worker가 이미 실행 중입니다.") from None
    except (ImportError, OSError, ValueError) as exc:
        raise SystemExit(f"실행 실패 ({type(exc).__name__}): {exc}") from None


if __name__ == "__main__":
    main()
