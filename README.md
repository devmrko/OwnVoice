# OwnVoice

[English](README.en.md)

현재 버전: **0.2.0a2 · 알파 2** ([릴리스](https://github.com/devmrko/OwnVoice/releases/tag/v0.2.0-alpha.2))

내 목소리로 텍스트·SRT를 WAV로 만드는 로컬 TTS 서비스입니다.
웹 화면과 HTTP API로 사용할 수 있습니다.
Qwen3-TTS·Chatterbox 모델 선택, CUDA/Apple Silicon 자동 선택, 구간 재생성,
SRT 시간 맞춤과 실제 처리 기록에 기반한 진행 상황을 제공합니다.

## 설치

Python·uv가 없어도 됩니다. GitHub **Code → Download ZIP**으로 받아 압축을 풀고,
FFmpeg를 준비한 뒤 Windows는 `start.cmd`, macOS·Linux는 `sh start.sh`를 실행하세요.
uv와 Python 3.12를 프로젝트 내부에 준비합니다. NVIDIA Windows는 `start.cmd -Cuda`를 사용합니다.
[플랫폼별 설치·지원 범위](docs/platforms.md)에 상세 절차가 있습니다.

이미 Python과 uv가 설치된 개발 환경에서는 아래 명령도 사용할 수 있습니다.

```sh
# macOS (Homebrew)
brew install ffmpeg sox

# Ubuntu/Debian에서는 대신 실행
# sudo apt-get install ffmpeg sox libsndfile1

git clone https://github.com/devmrko/OwnVoice.git
cd OwnVoice
uv sync --locked --extra tts
uv run --locked --extra tts ownvoice doctor
uv run --locked --extra tts ownvoice download-model
uv run --locked --extra tts ownvoice start
```

브라우저: **http://127.0.0.1:8765**. 종료는 실행한 터미널에서 **Ctrl+C**입니다.
`start`는 웹과 worker를 함께 실행하고 함께 종료합니다. 사용 중인 포트나 중복 worker는 거부합니다.

Python 패키지와 TTS 모델 다운로드에는 인터넷이 필요합니다.

## 로컬 TTS API

앱을 실행하면 웹과 같은 주소 `http://127.0.0.1:8765`에서 API를 사용할 수 있습니다.
웹에서 목소리를 등록한 뒤 `/v1/voices`가 반환하는 ID를 `VOICE_ID`에 넣으세요.
API로 만든 작업도 웹의 작업 내역에 표시됩니다.

```sh
# 등록한 목소리와 사용 가능한 모델 조회
curl http://127.0.0.1:8765/v1/voices
curl http://127.0.0.1:8765/v1/models

# 텍스트 합성 후 WAV 저장
curl --fail-with-body http://127.0.0.1:8765/v1/audio/speech \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen-small","voice":"VOICE_ID","input":"안녕하세요.","language":"Korean","response_format":"wav"}' \
  --output speech.wav
```

위 예제는 macOS·Linux 셸 기준입니다. HTTP 오류가 나면 출력 파일은 음성이 아닌
오류 응답일 수 있습니다. 모델은 `qwen`, `qwen-small`, `chatterbox` 중 선택합니다.
현재 WAV만 지원하며 OpenAI 음성 요청 형식의 일부를 지원합니다.

긴 대본·SRT는 작업을 등록하고 SSE로 진행 상황을 받습니다.

```sh
# job.json: model, voice, input, language와 mode("text" 또는 "srt") 지정
curl --fail-with-body http://127.0.0.1:8765/v1/jobs \
  -H 'Content-Type: application/json' --data-binary @job.json

# 응답의 id를 JOB_ID에 입력
curl -N http://127.0.0.1:8765/v1/jobs/JOB_ID/events
curl --fail http://127.0.0.1:8765/v1/jobs/JOB_ID/audio --output narration.wav
```

| API | 기능 |
|---|---|
| `POST /v1/audio/speech` | 합성 완료 후 WAV 반환 |
| `POST /v1/jobs` | 텍스트·SRT 작업 등록, 즉시 작업 ID 반환 |
| `GET /v1/jobs/{id}` | 상태·실측 시간·예상 남은 시간 조회 |
| `GET /v1/jobs/{id}/events` | SSE 진행 상황·구간 준비·완료 알림 |
| `GET /v1/jobs/{id}/audio` | 완성된 WAV 다운로드 |

SSE는 진행 알림과 완성된 구간의 음성 URL을 전달합니다. 합성 도중 음성을 조금씩
전송하는 기능은 아직 지원하지 않습니다. 예상 남은 시간은 실측 기록이 쌓인 뒤 표시합니다.
일반 합성 요청은 최대 600초 대기하며, 시간 초과나 연결 종료 후에도 작업은 계속됩니다.
오래 걸리는 요청은 `/v1/jobs`를 사용하세요. 현재는 인증 없는 로컬 전용 서비스입니다.

[전체 API 명세·SRT 입력·Python/Java 예제](docs/api.md) ·
[실행 중인 서버의 Swagger UI](http://127.0.0.1:8765/docs)

## 모델 다운로드

기본 모델은 `Qwen/Qwen3-TTS-12Hz-1.7B-Base`입니다.
`download-model`은 가중치·설정·speech tokenizer를 Hugging Face 캐시에 받습니다.
중간에 중단되면 같은 명령을 다시 실행하세요. 캐시 파일을 재사용합니다.
다운로드를 생략해도 최초 합성에서 자동으로 받지만, 사전에 받으면 설치 문제를 먼저 확인할 수 있습니다.
다운로드는 GPU에 모델을 올리거나 음성을 생성하지 않습니다.

```sh
# 인터넷 없이 기존 캐시 파일 확인 (실제 추론 검증은 아님)
uv run --locked --extra tts ownvoice download-model --offline

# 다운로드가 완료된 환경에서 네트워크 없이 실행
HF_HUB_OFFLINE=1 uv run --locked --extra tts ownvoice start
```

캐시 위치는 기본 `~/.cache/huggingface`이며 `HF_HOME`으로 바꿀 수 있습니다.
모델과 패키지는 저장소에 포함하지 않습니다. 여유 디스크와 메모리가 필요하며,
장치 이름만으로 속도를 보장하지 않습니다. 최초 로딩과 합성 시간은 별도로 표시합니다.
공식 모델 사용법과 모델 라이선스는 [Qwen 모델 페이지](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-Base)를 확인하세요.

## 화면 언어

상단 **화면 언어**에서 한국어·영어를 선택합니다. 선택은 브라우저에 저장됩니다.
화면 언어와 음성 생성 언어는 별개이며, 대본이나 작업 데이터는 번역하지 않습니다.

## 사용

1. 목소리 관리에서 3~60초 녹음 또는 음성 파일과 정확한 대본을 등록합니다.
2. 음성 생성에서 목소리를 선택하고 텍스트 또는 UTF-8 SRT를 입력합니다.
3. 작업 내역에서 진행률·실측 시간·예상 남은 합성 시간을 확인합니다.
4. 구간별 미리듣기와 수정·재생성 후 단일 WAV를 다운로드합니다.

예상 시간은 이번 실행에서 측정한 2개 이상의 구간 기록으로 계산합니다.
측정 기록이 부족하면 예상값을 만들지 않습니다. 로딩 막대는 진행 중임을 나타내며
다운로드율이나 추정 로딩 완료율을 의미하지 않습니다.

## 종료·재시작

- `start` 터미널에서 Ctrl+C로 웹과 worker를 종료합니다. 브라우저를 닫아도 작업은 계속됩니다.
- 같은 디렉터리에서 `start`를 다시 실행하면 중단된 작업을 복구합니다.
- DB에 완료로 저장된 구간은 재사용하고, 중단된 구간은 다시 합성합니다.
- 모델은 재다운로드 없이 캐시를 사용하지만 프로세스 재시작 시 메모리 로딩은 다시 합니다.
- 녹음·작업 DB·생성 WAV는 `.data/`에 저장합니다. 보존하려면 이 폴더를 지우지 마세요.
- 업데이트 전에는 종료한 뒤 `.data/`를 백업하고 `git pull`, `uv sync --locked --extra tts`를 실행하세요.

웹과 worker를 따로 운용할 수도 있습니다. 두 터미널에서 같은 디렉터리를 사용하세요.

```sh
uv run --locked --extra tts ownvoice web
uv run --locked --extra tts ownvoice worker
# 각 터미널에서 Ctrl+C로 개별 종료
```

| 환경변수 | 기본값 | 용도 |
|---|---|---|
| `OWNVOICE_DATA_DIR` | `.data` | 데이터 경로. 다른 경로에서 실행한다면 절대 경로 권장 |
| `OWNVOICE_DEVICE` | `auto` | `auto`, `cuda`, `mps`, `cpu` |
| `OWNVOICE_MODEL` | `Qwen/Qwen3-TTS-12Hz-1.7B-Base` | 참조 복제를 지원하는 Base 모델 ID 또는 로컬 경로 |
| `OWNVOICE_SRT_MAX_ATTEMPTS` | `3` | SRT 구간별 최대 합성 횟수 (최초 포함, 1~5) |
| `HF_HOME` | Hugging Face 기본 캐시 | 모델 캐시 경로 |

웹과 worker에 같은 환경변수를 적용하세요. `.env`를 자동으로 읽지는 않습니다.
포트 변경: `ownvoice start --port 8766`. 웹 화면만 확인하려면 `uv sync --locked` 후
`uv run --locked ownvoice web`을 사용하세요.

## 문제 확인

- `doctor`가 FFmpeg 또는 TTS 설치 오류를 보고하면 설치 단계를 다시 확인합니다.
- NVIDIA에서 CPU로 표시되면 [PyTorch 공식 설치 안내](https://pytorch.org/get-started/locally/)에서
  드라이버에 맞는 빌드를 확인하세요. CUDA 실기기는 아직 검증하지 않았습니다.
- Mac에서 MPS를 못 찾으면 Apple Silicon 네이티브 Python과 일반 터미널에서 확인합니다.
- 다운로드 오류는 네트워크·프록시·캐시 디스크 용량을 확인하고 `download-model`을 다시 실행합니다.
- 메모리 부족 시 다른 GPU 앱을 종료하거나 더 작은 `Qwen/Qwen3-TTS-12Hz-0.6B-Base`를 설정합니다.
  작은 모델의 음질과 속도는 별도 검증이 필요합니다.
- 실패한 작업은 원인을 해결한 뒤 작업 상세에서 재시도합니다.
- 중복 worker 오류가 나면 기존 worker를 종료하세요. 실행 중인 worker의 lock 파일을 지우지 마세요.

## 시간 맞춤과 한계

SRT 시작 시각을 유지하며 짧은 발화 뒤에는 무음을 넣습니다. 긴 발화는 음높이를
유지하면서 최대 1.15배까지 가속합니다. 그래도 초과하면 같은 문장으로 최대 3회
합성하고, 시간에 맞는 결과가 나오면 자동으로 합칩니다. 모두 초과하면 가장 짧은
결과와 배정 시간·합성 횟수를 표시합니다. 이 경우 검토 필요로 표시하고 최종 WAV
다운로드를 막습니다. 원문 변경, 음성 자르기, 뒤 자막 밀기는 하지 않습니다.
겹치는 자막은 지원하지 않습니다. 출력 길이는 마지막 자막 종료 시각입니다.
긴 문장에서는 모델 출력이 불완전할 수 있으므로 구간을 나누고 미리듣기로 확인하세요.

- 참조 기반 복제이며 사용자별 모델 재학습은 아닙니다.
- 단일 사용자 localhost용입니다. 인터넷에 서버를 직접 노출하는 용도는 지원하지 않습니다.
- 녹음은 localhost 또는 HTTPS에서 가능합니다. 본인 또는 사용 허락을 받은 목소리를 사용하세요.
- 취소 버튼·프로필 삭제는 아직 지원하지 않습니다.
- 실제 Apple Silicon 추론은 확인했습니다. 음질은 참조 음성·대본에 따라 달라집니다.

## 음성 생성 모델

생성 설정에서 Qwen3-TTS 1.7B, 경량 Qwen3-TTS 0.6B, Chatterbox Multilingual V3를
선택합니다. 0.6B는 추가 설치 없이 사용하며 첫 선택 시 모델을 다운로드합니다.
작업마다 모델을 저장하고, 전환 시 이전 모델을 메모리에서 해제합니다.
경량 모델의 속도·품질은 실제 생성 결과로 비교하세요.

Chatterbox는 선택 설치입니다. 기존 Qwen 환경과 별도로 설치됩니다.

```sh
# macOS / Linux
./uvw sync --locked --project engines/chatterbox --python 3.12 --managed-python
```

```powershell
# Windows PowerShell
.\uvw.ps1 sync --locked --project engines/chatterbox --python 3.12 --managed-python
# Windows NVIDIA: 별도 환경에도 CUDA PyTorch 설치
.\uvw.ps1 pip install --python engines/chatterbox/.venv/Scripts/python.exe torch==2.6.0 torchaudio==2.6.0 --torch-backend=auto --reinstall
```

설치 후 화면을 새로고침하세요. 첫 생성 시 모델이 다운로드됩니다.
Chatterbox는 참조 음성만 사용하며, 언어를 직접 선택해야 합니다.
생성 음성에는 upstream의 PerTh 워터마크가 유지됩니다.
Windows CUDA의 실제 Chatterbox 합성은 NVIDIA 장비에서 별도 검증이 필요합니다.

## 개발 명령

```sh
uv sync --locked
uv run --locked ruff check src tests scripts
uv run --locked ruff format --check src tests scripts
uv run --locked mypy
uv run --locked pytest
uv build
uv run --locked python scripts/verify_wheel.py
```

테스트는 임시 데이터와 테스트용 합성기를 사용합니다. 실행 중인 사용자 작업을 변경하지 않습니다.
- [데이터 저장 파일·백업·복구](docs/storage.md)
- [로컬 TTS API · SSE · Python/Java 호출 예제](docs/api.md)
- [아키텍처와 처리 흐름](docs/architecture.md)
- [라이브러리 명세](docs/libraries.md) · [전체 잠금 버전](docs/dependencies-lock.md)
- [Windows CUDA·첫 실행](docs/platforms.md)
- [설계](docs/design/ownvoice.md) · [검증 기록](docs/validation.md)
- [저장소 정리 내역](docs/repository-audit.md) · [포함한 소스](vendor/README.md)

## 라이선스

OwnVoice는 [MIT](LICENSE) 라이선스입니다.
Qwen 모델과 외부 패키지에는 각각의 라이선스가 적용됩니다.
