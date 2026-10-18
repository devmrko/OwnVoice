import shutil
import subprocess
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import SecretStr
from python_foundation.database import SqlAlchemyUnitOfWork, create_database, sessions
from python_foundation.errors import BusinessError, ErrorCategory, ErrorSpec
from python_foundation.settings import FoundationSettings

from ownvoice.audio import convert_reference
from ownvoice.config import Settings
from ownvoice.domain import JobRequest, invalid, parse_segments
from ownvoice.progress import job_progress
from ownvoice.repository import Base, Repository


def missing() -> BusinessError:
    return BusinessError(ErrorSpec("NOT_FOUND", ErrorCategory.NOT_FOUND, "항목을 찾을 수 없습니다."))


def conflict() -> BusinessError:
    return BusinessError(
        ErrorSpec("JOB_BUSY", ErrorCategory.CONFLICT, "대기·실행 중인 작업은 수정할 수 없습니다.")
    )


class Service:
    def __init__(self, settings: Settings):
        self.settings = settings
        settings.prepare()
        self.engine = create_database(
            FoundationSettings(
                database_url=SecretStr(f"sqlite:///{settings.data_dir.resolve() / 'ownvoice.db'}")
            )
        )
        Base.metadata.create_all(self.engine)
        self.factory = sessions(self.engine)

    def uow(self) -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(self.factory)

    def get(self, kind: str, key: str) -> dict[str, Any]:
        with self.uow() as work:
            row = Repository(work.session).get(kind, key)
            if row is None:
                raise missing()
            result = {"id": row.id, "created_at": row.created_at, **row.data}
            if kind == "job":
                result["progress"] = job_progress(result)
            return result

    def list(self, kind: str) -> list[dict[str, Any]]:
        with self.uow() as work:
            return [
                {"id": r.id, "created_at": r.created_at, **r.data}
                for r in Repository(work.session).list(kind)
            ]

    def profile(self, name: str, transcript: str, content: bytes) -> dict[str, Any]:
        if (
            not name.strip()
            or len(name) > 80
            or len(transcript) > 3000
            or not content
            or len(content) > 20_000_000
        ):
            raise invalid("이름(80자 이하), 대본(3,000자 이하), 음성 파일(20MB 이하)을 확인해 주세요.")
        key = str(uuid4())
        folder = self.settings.data_dir / "profiles" / key
        folder.mkdir()
        source = folder / "upload"
        try:
            source.write_bytes(content)
            convert_reference(source, folder / "reference.wav")
            source.unlink()
            with self.uow() as work:
                Repository(work.session).add(
                    "profile", key, {"name": name.strip(), "transcript": transcript.strip()}
                )
        except (ValueError, subprocess.SubprocessError, FileNotFoundError) as exc:
            shutil.rmtree(folder)
            raise invalid(
                "음성 변환에 실패했습니다. FFmpeg 설치와 3~60초 음성 파일을 확인해 주세요."
            ) from exc
        except Exception:
            shutil.rmtree(folder)
            raise
        return self.get("profile", key)

    def create_job(self, request: JobRequest) -> dict[str, Any]:
        profile = self.get("profile", request.profile_id)
        segments = parse_segments(request.mode, request.content)
        key = str(uuid4())
        with self.uow() as work:
            Repository(work.session).add(
                "job",
                key,
                {
                    **request.model_dump(),
                    "profile_name": profile["name"],
                    "status": "queued",
                    "stage": "queued",
                    "error": None,
                    "segments": [s.model_dump() for s in segments],
                },
            )
        return self.get("job", key)

    def edit(self, key: str, index: int | None = None, text: str | None = None) -> dict[str, Any]:
        with self.uow() as work:
            row = Repository(work.session).get("job", key)
            if row is None:
                raise missing()
            data = dict(row.data)
            if data["status"] in ("queued", "running"):
                raise conflict()
            segments = [dict(s) for s in data["segments"]]
            if index is not None:
                if not 0 <= index < len(segments):
                    raise missing()
                segments[index].update(text=text, status="pending", duration_ms=None, speed=1.0)
                (self.settings.data_dir / "jobs" / key / f"{index}.wav").unlink(missing_ok=True)
            else:
                for segment in segments:
                    if segment["status"] == "needs_review":
                        segment["status"] = "pending"
                        (self.settings.data_dir / "jobs" / key / f"{segment['index']}.wav").unlink(
                            missing_ok=True
                        )
            data.update(
                status="queued",
                stage="queued",
                started_at=None,
                finished_at=None,
                current_segment=None,
                synthesis_timings=[],
                phase_seconds={},
                first_audio_ready_seconds=None,
                execution_device=None,
                error=None,
                segments=segments,
            )
            row.data = data
        return self.get("job", key)

    def update_job(self, key: str, data: dict[str, Any]) -> None:
        with self.uow() as work:
            row = Repository(work.session).get("job", key)
            if row is None:
                raise missing()
            row.data = {k: v for k, v in data.items() if k not in ("id", "created_at", "progress")}

    def recover(self) -> None:
        with self.uow() as work:
            for row in Repository(work.session).list("job"):
                if row.data["status"] == "running":
                    row.data = {
                        **row.data,
                        "status": "queued",
                        "stage": "queued",
                        "started_at": None,
                        "finished_at": None,
                    }

    def claim(self) -> dict[str, Any] | None:
        # The worker holds an OS lock for its entire lifetime. UI cannot claim jobs.
        with self.uow() as work:
            for row in reversed(Repository(work.session).list("job")):
                if row.data["status"] == "queued":
                    row.data = {
                        **row.data,
                        "status": "running",
                        "stage": "preparing",
                        "started_at": time.time(),
                        "finished_at": None,
                        "synthesis_timings": [],
                        "phase_seconds": {},
                        "first_audio_ready_seconds": None,
                        "execution_device": None,
                        "error": None,
                    }
                    return {"id": row.id, **row.data}
        return None

    def audio_path(self, key: str, index: int | None = None) -> Path:
        job = self.get("job", key)
        if index is None and job["status"] != "completed":
            raise BusinessError(
                ErrorSpec(
                    "NOT_READY", ErrorCategory.CONFLICT, "검토와 생성을 완료한 뒤 다운로드할 수 있습니다."
                )
            )
        if index is not None and not 0 <= index < len(job["segments"]):
            raise missing()
        path = self.settings.data_dir / "jobs" / key / ("output.wav" if index is None else f"{index}.wav")
        if not path.is_file():
            raise missing()
        return path
