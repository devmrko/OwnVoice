# OwnVoice

Current version: **0.2.0a2 · Alpha 2** ([release](https://github.com/devmrko/OwnVoice/releases/tag/v0.2.0-alpha.2)).

Local TTS service for text and SRT narration, with Qwen3-TTS and Chatterbox.
Use the web interface or HTTP API with SSE progress notifications.
Export a single WAV with subtitle timing. The interface supports English and Korean.

## Start without Python or uv

Download **Code → Download ZIP** and extract it.

1. Install FFmpeg and ensure `ffmpeg` is on PATH.
2. Windows: run `start.cmd`; for NVIDIA run `start.cmd -Cuda`.
3. macOS/Linux: run `sh start.sh`.
4. Open http://127.0.0.1:8765. Stop both processes with Ctrl+C in the terminal.

The launcher installs uv and Python 3.12 under `.tools/`, then dependencies under
`.venv/`. It does not modify global Python or PATH. Internet access is required
for installation and the first model download. The model is downloaded on first use.
FFmpeg is a separate prerequisite; the launcher prints installation instructions if missing.

Register 3–60 seconds of reference audio and its transcript, then enter text or
load a UTF-8 SRT. Review generated segments and download the finished WAV.
The interface language selector does not change speech language or user content.

## Local TTS API

Start the app normally. The API shares `http://127.0.0.1:8765` with the web UI.
Register a voice in the UI and replace `VOICE_ID` with its ID from `/v1/voices`.
API jobs also appear in the web job history.

```sh
curl http://127.0.0.1:8765/v1/voices
curl http://127.0.0.1:8765/v1/models

curl --fail-with-body http://127.0.0.1:8765/v1/audio/speech \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen-small","voice":"VOICE_ID","input":"Hello.","language":"English","response_format":"wav"}' \
  --output speech.wav
```

These examples use macOS/Linux shell syntax. On HTTP failure, the output file may
contain an error response instead of audio. Choose `qwen`, `qwen-small` or `chatterbox`.
Only WAV output is supported; this implements a subset of the OpenAI speech request format.

For long scripts and SRT, submit a job and receive SSE progress:

```sh
# job.json contains model, voice, input, language and mode ("text" or "srt")
curl --fail-with-body http://127.0.0.1:8765/v1/jobs \
  -H 'Content-Type: application/json' --data-binary @job.json

# Replace JOB_ID with the returned id
curl -N http://127.0.0.1:8765/v1/jobs/JOB_ID/events
curl --fail http://127.0.0.1:8765/v1/jobs/JOB_ID/audio --output narration.wav
```

| API | Purpose |
|---|---|
| `POST /v1/audio/speech` | Wait for synthesis and return WAV |
| `POST /v1/jobs` | Submit text/SRT and immediately return a job ID |
| `GET /v1/jobs/{id}` | Status, measured elapsed time and estimated remaining time |
| `GET /v1/jobs/{id}/events` | SSE progress, segment readiness and completion |
| `GET /v1/jobs/{id}/audio` | Download the completed WAV |

SSE carries progress and completed-segment audio URLs, not incremental audio during
synthesis. ETA remains null until enough measured samples exist. Speech requests wait
up to 600 seconds; jobs continue after timeout or disconnect. Prefer `/v1/jobs` for
long requests. This release is local-only and does not require an API key.

[Full API contract, SRT input and Python/Java examples](docs/api.md) ·
[Swagger UI on your running server](http://127.0.0.1:8765/docs)

## Data and timing

History is in `.data/ownvoice.db`; references are in `.data/profiles/`; segment
and final WAV files are in `.data/jobs/`. Stop the app and back up the entire
`.data/` directory, not just the database. Interrupted jobs resume on restart.

SRT timing is preserved with silence or up to 1.15× pitch-preserving speedup.
Overlong segments get up to 3 synthesis attempts. Unresolved segments require
review before export; speech is not truncated and subtitles are not shifted.

## Platform limits

Apple Silicon inference has been exercised. CI tests CPU functionality and packaging
on Linux, macOS and Windows. NVIDIA device selection is implemented, but actual
Windows/Linux CUDA inference and quality still require hardware validation.
`-Cuda` selects driver-compatible PyTorch wheels and may differ from the root lockfile;
keep using that launcher option. CPU test success does not certify CUDA inference.

Use your own voice or a voice you have permission to use. This is a single-user
localhost application, not an authenticated public server.

## Model selection

Choose Qwen3-TTS 1.7B, lightweight Qwen3-TTS 0.6B, or Chatterbox Multilingual V3
in generation settings. Qwen 0.6B needs no extra package installation; its weights
download on first use. Each job retains its engine. Switching unloads the previous
model. Compare actual speed and quality rather than assuming smaller is faster.

Chatterbox uses a separate optional environment:

```sh
./uvw sync --locked --project engines/chatterbox --python 3.12 --managed-python
```

On Windows use `.\uvw.ps1` instead of `./uvw`. For NVIDIA also run:

```powershell
.\uvw.ps1 pip install --python engines/chatterbox/.venv/Scripts/python.exe torch==2.6.0 torchaudio==2.6.0 --torch-backend=auto --reinstall
```

Refresh the page after installation. Chatterbox uses reference audio without a
transcript and requires an explicit language. Upstream PerTh watermarking is retained.
Windows CUDA inference still needs hardware validation.

## Technical documentation

The detailed technical documents are currently in Korean:

- [Storage, backup and recovery](docs/storage.md)
- [Local TTS API, SSE, Python/Java examples](docs/api.md)
- [Architecture](docs/architecture.md)
- [Libraries](docs/libraries.md) and [locked versions](docs/dependencies-lock.md)
- [Platform installation](docs/platforms.md)
- [Validation](docs/validation.md)

OwnVoice uses the MIT license. External packages
and Qwen model weights retain their respective licenses.
