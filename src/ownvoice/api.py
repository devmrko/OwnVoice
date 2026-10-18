"""Versioned local API; all synthesis uses the existing durable worker queue."""

import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Any, Literal

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.concurrency import run_in_threadpool

from ownvoice.domain import JobRequest, SegmentEdit
from ownvoice.engine_catalog import engine_catalog
from ownvoice.service import Service

TERMINAL = {"completed", "failed", "needs_review"}
POLL_SECONDS = 1.0
SPEECH_TIMEOUT = 600.0


class SpeechRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: Literal["qwen", "qwen-small", "chatterbox"] = "qwen"
    voice: str = Field(min_length=1)
    input: str = Field(min_length=1, max_length=100_000)
    response_format: Literal["wav"] = "wav"
    speed: float = Field(default=1.0, ge=1.0, le=1.0)
    stream_format: Literal["audio"] = "audio"
    language: Literal["Korean", "English", "Japanese", "Chinese", "Auto"] = "Korean"

    @field_validator("input")
    @classmethod
    def nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Input is empty")
        return value

    def job_request(self, mode: Literal["text", "srt"] = "text") -> JobRequest:
        return JobRequest(
            engine=self.model, profile_id=self.voice, mode=mode, content=self.input, language=self.language
        )


class AsyncJobRequest(SpeechRequest):
    mode: Literal["text", "srt"] = "text"


def public_job(job: dict[str, Any]) -> dict[str, Any]:
    key = job["id"]
    base = f"/v1/jobs/{key}"
    return {
        "id": key,
        "created_at": job.get("created_at"),
        "status": job["status"],
        "model": job.get("engine", "qwen"),
        "voice": job["profile_id"],
        "mode": job["mode"],
        "language": job["language"],
        "error": job.get("error"),
        "progress": job["progress"],
        "url": base,
        "events_url": f"{base}/events",
        "audio_url": f"{base}/audio" if job["status"] == "completed" else None,
        "segments": [
            {
                **segment,
                "audio_url": f"{base}/segments/{segment['index']}/audio"
                if segment["status"] == "completed"
                else None,
            }
            for segment in job["segments"]
        ],
    }


def router(service: Service) -> APIRouter:
    api = APIRouter(prefix="/v1", tags=["Local TTS API"])

    @api.get("/models")
    def models() -> dict[str, Any]:
        return {
            "object": "list",
            "data": [
                {
                    **model,
                    "object": "model",
                    "owned_by": "local",
                    "response_formats": ["wav"],
                    "incremental_audio": False,
                }
                for model in engine_catalog(service.settings)
            ],
        }

    @api.get("/voices")
    def voices() -> dict[str, Any]:
        return {
            "object": "list",
            "data": [{"id": voice["id"], "name": voice["name"]} for voice in service.list("profile")],
        }

    @api.post("/jobs", status_code=202)
    def create(body: AsyncJobRequest, response: Response) -> dict[str, Any]:
        job = public_job(service.create_job(body.job_request(body.mode)))
        response.headers["Location"] = job["url"]
        return job

    @api.get("/jobs/{key}")
    def get(key: str) -> dict[str, Any]:
        return public_job(service.get("job", key))

    @api.post("/jobs/{key}/retry", status_code=202)
    def retry(key: str) -> dict[str, Any]:
        return public_job(service.edit(key))

    @api.patch("/jobs/{key}/segments/{index}", status_code=202)
    def edit(key: str, index: int, body: SegmentEdit) -> dict[str, Any]:
        return public_job(service.edit(key, index, body.text))

    @api.get("/jobs/{key}/audio")
    def audio(key: str) -> FileResponse:
        return FileResponse(service.audio_path(key), media_type="audio/wav", filename=f"ownvoice-{key}.wav")

    @api.get("/jobs/{key}/segments/{index}/audio")
    def segment_audio(key: str, index: int) -> FileResponse:
        return FileResponse(service.audio_path(key, index), media_type="audio/wav")

    @api.get("/jobs/{key}/events")
    async def events(key: str, request: Request) -> StreamingResponse:
        # Validate before committing HTTP 200 headers.
        await run_in_threadpool(service.get, "job", key)

        async def stream() -> AsyncIterator[str]:
            ready: set[int] = set()
            while not await request.is_disconnected():
                job = public_job(await run_in_threadpool(service.get, "job", key))
                for segment in job["segments"]:
                    if segment["status"] != "completed":
                        ready.discard(segment["index"])
                    elif segment["index"] not in ready:
                        ready.add(segment["index"])
                        yield f"event: segment_ready\ndata: {json.dumps(segment, ensure_ascii=False)}\n\n"
                event = job["status"] if job["status"] in TERMINAL else "progress"
                yield f"event: {event}\ndata: {json.dumps(job, ensure_ascii=False)}\n\n"
                if job["status"] in TERMINAL:
                    return
                await asyncio.sleep(POLL_SECONDS)

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    @api.post("/audio/speech")
    async def speech(body: SpeechRequest, request: Request) -> Response:
        job = await run_in_threadpool(service.create_job, body.job_request())
        key = job["id"]
        headers = {"X-OwnVoice-Job-Id": key, "Location": f"/v1/jobs/{key}"}
        deadline = time.monotonic() + SPEECH_TIMEOUT
        while True:
            job = await run_in_threadpool(service.get, "job", key)
            if job["status"] == "completed":
                path = await run_in_threadpool(service.audio_path, key)
                return FileResponse(path, media_type="audio/wav", headers=headers)
            if job["status"] in TERMINAL:
                return JSONResponse(
                    {"error": {"code": job["status"], "message": job.get("error")}, "job": public_job(job)},
                    status_code=409,
                    headers=headers,
                )
            if time.monotonic() >= deadline:
                return JSONResponse(
                    {
                        "error": {
                            "code": "wait_timeout",
                            "message": "Synthesis continues. Retrieve this job instead of resubmitting.",
                        },
                        "job": public_job(job),
                    },
                    status_code=504,
                    headers=headers,
                )
            if await request.is_disconnected():
                return Response(status_code=204, headers=headers)
            await asyncio.sleep(POLL_SECONDS)

    return api
