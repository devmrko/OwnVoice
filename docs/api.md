# Local TTS API / 로컬 TTS API

Run OwnVoice normally (`./start.sh`, Windows `start.cmd`). The web UI and API use
`http://127.0.0.1:8765` and the same SQLite job queue, voice profiles and serial GPU worker.
Interactive schema: [/docs](http://127.0.0.1:8765/docs), JSON: `/openapi.json`.
The API does not start another model process per request.

기존 실행 명령으로 웹과 API를 함께 사용합니다. 웹에서 등록한 목소리를 API에서도
사용하며 API 작업은 웹 작업 내역에도 표시됩니다. CUDA/MPS 선택은 기존 worker가
처리합니다. API 서버만 실행하면 작업은 대기하므로 `ownvoice start`로 실행하세요.

## Interface

| Method | Path | Result |
|---|---|---|
| GET | `/v1/models` | `data`: model IDs, names, installation availability and supported formats |
| GET | `/v1/voices` | `data`: registered voice IDs and display names |
| POST | `/v1/audio/speech` | Wait for synthesis, return `audio/wav` |
| POST | `/v1/jobs` | HTTP 202, job state and `Location` header |
| GET | `/v1/jobs/{id}` | Current job state, measured progress, segments and audio URLs |
| GET | `/v1/jobs/{id}/events` | SSE snapshots and terminal notification |
| GET | `/v1/jobs/{id}/audio` | Final WAV; HTTP 409 until completed |
| GET | `/v1/jobs/{id}/segments/{index}/audio` | Existing segment WAV (zero-based index) |
| POST | `/v1/jobs/{id}/retry` | Requeue a stopped job; HTTP 409 if already active |
| PATCH | `/v1/jobs/{id}/segments/{index}` | `{"text":"Replacement"}`; requeue edited segment |

`available` reports the engine installation, not that its weights are cached or
that synthesis was verified. First use may download/load models.
Voice registration remains in the web UI (or existing multipart `/api/profiles` API).

## Short text / 일반 텍스트

Use an ID from `/v1/voices`, not the voice's display name.

```bash
curl http://127.0.0.1:8765/v1/voices
curl http://127.0.0.1:8765/v1/audio/speech \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen-small","voice":"VOICE_ID","input":"안녕하세요.","response_format":"wav","language":"Korean"}' \
  --output speech.wav
```

Required: `voice`, `input`. Defaults: `model=qwen`, `response_format=wav`,
`language=Korean`, `speed=1.0`, `stream_format=audio`.
Models: `qwen`, `qwen-small`, `chatterbox`. Languages: `Korean`, `English`,
`Japanese`, `Chinese`, `Auto`; Chatterbox requires an explicit language.
Only WAV, speed 1.0 and complete-file audio responses are supported. Unknown
fields, other formats, speeds and `stream_format=sse` return HTTP 422.

This is an OpenAI-shaped **speech request subset**, not full OpenAI API compatibility.
No incremental audio is emitted during synthesis. Error responses use the existing
OwnVoice problem format for validation/domain errors; wait failures include `error`
and a `job` snapshot. Clients must check HTTP status before saving response bytes.

The response includes `X-OwnVoice-Job-Id` and `Location`. Server wait limit: 600 seconds
including queue time. HTTP 504 means the job **continues**; retrieve `Location` instead
of submitting again. HTTP 409 indicates synthesis failed or needs review.
Client disconnects also leave jobs queued/running. For durable access to the ID before
synthesis, use `/v1/jobs`. No automatic submission deduplication is provided; blindly
retrying POST can create duplicate jobs.

## SRT and long text / 자막·긴 대본

```python
import json
import urllib.request
from pathlib import Path

base = "http://127.0.0.1:8765"
body = {
    "model": "qwen-small", "voice": "VOICE_ID", "mode": "srt",
    "input": Path("subtitles.srt").read_text(encoding="utf-8-sig"),
    "language": "Korean",
}
request = urllib.request.Request(base + "/v1/jobs", json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
with urllib.request.urlopen(request) as response:
    job = json.load(response)
print(job["id"], base + job["events_url"])
```

Use `mode=text` (default) for a long script. The same input limits as the UI apply:
100,000 characters total, up to 500 segments, 1,000 characters per segment;
SRT must be ordered, nonoverlapping and at most two hours.

```bash
curl -N http://127.0.0.1:8765/v1/jobs/JOB_ID/events
curl --fail http://127.0.0.1:8765/v1/jobs/JOB_ID/audio --output narration.wav
```

SSE events:

- `progress`: full current job snapshot about once per second, including queued state.
- `segment_ready`: completed segment metadata and `audio_url`. SRT timing adjustment
  has finished for that segment. `needs_review` segments do not emit readiness.
- `completed`: final snapshot with `audio_url`, then stream closes.
- `failed`, `needs_review`: final snapshot, then stream closes; no final WAV URL.

Progress uses existing measurements: `elapsed_seconds`, `eta_seconds`, `percent`,
`stage`, and `performance`. ETA is `null` until sufficient measured samples exist.
Audio URLs are relative to the API origin. SSE contains JSON, not audio bytes.
Segment audio is speech for that segment; use start/end timestamps for placement,
or download the final WAV with timeline silence already applied.

Reconnect receives the current snapshot and currently completed segments again.
There is no historical event log or `Last-Event-ID` replay. Deduplicate segment events
by job ID and segment index. Browser EventSource users should call `close()` on a
terminal event to prevent automatic reconnection. Retrying/editing a job invalidates
old results; fetch current state after the mutation.

SSE는 진행 상황 통지용이며 합성 속도를 높이지 않습니다. 연결이 끊겨도 작업은
계속됩니다. 재연결 시 현재 상태를 다시 받으며 완료 이벤트를 받으면 연결을 닫습니다.

## Java 11+ example

```java
var client = java.net.http.HttpClient.newHttpClient();
var body = "{\"model\":\"qwen-small\",\"voice\":\"VOICE_ID\",\"input\":\"Hello.\",\"language\":\"English\"}";
var request = java.net.http.HttpRequest.newBuilder(
        java.net.URI.create("http://127.0.0.1:8765/v1/audio/speech"))
    .header("Content-Type", "application/json")
    .POST(java.net.http.HttpRequest.BodyPublishers.ofString(body)).build();
var response = client.send(request, java.net.http.HttpResponse.BodyHandlers.ofByteArray());
if (response.statusCode() != 200) throw new IllegalStateException("HTTP " + response.statusCode());
java.nio.file.Files.write(java.nio.file.Path.of("speech.wav"), response.body());
```

## Local boundary and storage

No API key is required on loopback. The server binds to `127.0.0.1`; this release does
not provide LAN hosting, multi-user isolation or authenticated remote access.
`/v1` JSON requests do not require the web UI's `X-OwnVoice` header. Non-JSON mutations
still require `X-OwnVoice: 1`; cross-origin browser requests remain rejected.
For a bodyless retry send `Content-Type: application/json` or `X-OwnVoice: 1`.

Jobs and audio have the same retention as UI jobs: SQLite and `.data/jobs/{id}`;
see [storage](storage.md). API disconnects do not delete files or cancel synthesis.
