import json
import re
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from python_foundation.errors import BusinessError, ErrorCategory
from python_foundation.web import RequestContextMiddleware, problem
from starlette.middleware.trustedhost import TrustedHostMiddleware

from ownvoice.api import router
from ownvoice.config import Settings
from ownvoice.domain import JobRequest, SegmentEdit, invalid
from ownvoice.engine import runtime
from ownvoice.i18n import language, localize_job, translate
from ownvoice.progress import job_progress
from ownvoice.service import Service, missing


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    service = Service(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        service.engine.dispose()

    app = FastAPI(title="OwnVoice", lifespan=lifespan)
    app.state.service = service
    app.add_middleware(RequestContextMiddleware, max_request_bytes=21_000_000)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])

    @app.middleware("http")
    async def local_boundary(request: Request, call_next: Any) -> Response:
        locale = language(request.headers.get("accept-language", "ko"))

        def reject(code: str, message: str) -> Response:
            response = problem(403, code, translate(message, locale) or message)
            response.headers["Content-Language"] = locale
            return response

        origin = request.headers.get("origin")
        if origin and origin != f"{request.url.scheme}://{request.headers.get('host')}":
            return reject("ORIGIN_DENIED", "다른 사이트에서의 요청은 허용하지 않습니다.")
        # JSON-only v1 requests support ordinary API clients while rejecting
        # cross-site form submissions. Origin validation above remains mandatory.
        api_json = request.url.path.startswith("/v1/") and (
            request.headers.get("content-type", "").split(";", 1)[0].strip().lower() == "application/json"
        )
        if (
            request.method not in ("GET", "HEAD", "OPTIONS")
            and request.headers.get("x-ownvoice") != "1"
            and not api_json
        ):
            return reject("REQUEST_DENIED", "OwnVoice 화면에서 요청해 주세요.")
        if urlsplit(str(request.url)).hostname not in ("localhost", "127.0.0.1", "testserver"):
            return reject("HOST_DENIED", "로컬 접속만 지원합니다.")
        response: Response = await call_next(request)
        response.headers["Content-Language"] = locale
        response.headers["Vary"] = "Accept-Language"
        return response

    @app.exception_handler(BusinessError)
    async def business(request: Request, exc: BusinessError) -> Response:
        code = {
            ErrorCategory.VALIDATION: 400,
            ErrorCategory.NOT_FOUND: 404,
            ErrorCategory.CONFLICT: 409,
            ErrorCategory.UNAVAILABLE: 503,
        }[exc.error.category]
        return problem(
            code,
            exc.error.code,
            translate(exc.error.message, language(request.headers.get("accept-language", "ko")))
            or exc.error.message,
        )

    @app.exception_handler(RequestValidationError)
    async def validation(request: Request, exc: RequestValidationError) -> Response:
        message = translate(
            "입력 내용을 확인해 주세요.", language(request.headers.get("accept-language", "ko"))
        )
        return problem(422, "INVALID_INPUT", message or "Invalid input.")

    @app.get("/api/runtime")
    def environment(request: Request) -> dict[str, Any]:
        state = runtime(service.settings)
        try:
            heartbeat = json.loads((service.settings.data_dir / "worker.json").read_text())
            state["worker_online"] = time.time() - heartbeat["updated"] < 20
            state["inference_verified"] = state["worker_online"] and heartbeat.get(
                "inference_verified", False
            )
        except (FileNotFoundError, ValueError, KeyError):
            state["worker_online"] = False
        locale = language(request.headers.get("accept-language", "ko"))
        state["error"] = translate(state.get("error"), locale)
        for field in ("name", "memory_kind"):
            state["hardware"][field] = translate(state["hardware"].get(field), locale)
        return state

    @app.get("/api/profiles")
    def profiles() -> list[dict[str, Any]]:
        return service.list("profile")

    @app.get("/api/comparisons")
    def comparisons() -> list[str]:
        root = service.settings.data_dir / "diagnostics"
        return sorted(
            (
                p.name
                for p in root.glob("voice-comparison-*")
                if re.fullmatch(r"voice-comparison-\d{8}-\d{6}", p.name)
                and (p / "index.html").is_file()
                and ((p / "3-with.wav").is_file() or (p / "chatterbox-3.wav").is_file())
            ),
            reverse=True,
        )

    @app.get("/comparisons/{comparison}/{filename}")
    def comparison_file(comparison: str, filename: str) -> FileResponse:
        if not re.fullmatch(r"voice-comparison-\d{8}-\d{6}", comparison):
            raise missing()
        if not re.fullmatch(
            r"index\.html|reference-with\.wav|[1-3]-(?:with|without)\.wav|(?:qwen|qwen-small|chatterbox)-[1-3]\.wav",
            filename,
        ):
            raise missing()
        root = (service.settings.data_dir / "diagnostics").resolve()
        path = (root / comparison / filename).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise missing()
        return FileResponse(path)

    @app.post("/api/profiles", status_code=201)
    def profile(
        name: str = Form(...), transcript: str = Form(""), audio: UploadFile = File(...)
    ) -> dict[str, Any]:
        content = audio.file.read(20_000_001)
        return service.profile(name, transcript, content)

    @app.get("/api/jobs")
    def jobs(request: Request) -> list[dict[str, Any]]:
        return [
            {k: v for k, v in job.items() if k not in ("content", "segments")}
            | {
                "progress": job_progress(job),
                "total": len(job["segments"]),
                "done": sum(s["status"] == "completed" for s in job["segments"]),
            }
            for job in (
                localize_job(item, language(request.headers.get("accept-language", "ko")))
                for item in service.list("job")
            )
        ]

    @app.post("/api/jobs", status_code=201)
    def create(request: JobRequest) -> dict[str, Any]:
        return service.create_job(request)

    @app.get("/api/jobs/{key}")
    def job(key: str, request: Request) -> dict[str, Any]:
        return localize_job(service.get("job", key), language(request.headers.get("accept-language", "ko")))

    @app.post("/api/jobs/{key}/retry")
    def retry(key: str) -> dict[str, Any]:
        return service.edit(key)

    @app.patch("/api/jobs/{key}/segments/{index}")
    def edit(key: str, index: int, body: SegmentEdit) -> dict[str, Any]:
        return service.edit(key, index, body.text)

    @app.get("/api/jobs/{key}/audio")
    def audio(key: str) -> FileResponse:
        return FileResponse(service.audio_path(key), media_type="audio/wav", filename=f"ownvoice-{key}.wav")

    @app.get("/api/jobs/{key}/segments/{index}/audio")
    def segment_audio(key: str, index: int) -> FileResponse:
        if index < 0:
            raise invalid("잘못된 구간입니다.")
        return FileResponse(service.audio_path(key, index), media_type="audio/wav")

    app.include_router(router(service))

    static = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static), name="static")

    @app.get("/")
    def home() -> FileResponse:
        return FileResponse(static / "index.html")

    return app
