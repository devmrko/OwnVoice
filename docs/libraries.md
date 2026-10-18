# 라이브러리 명세

설치 계약은 root `pyproject.toml`, 정확한 버전·배포 파일 해시는 `uv.lock`이 기준입니다.
[전체 패키지와 잠금 버전](dependencies-lock.md)은 해당 lockfile에서 생성합니다.
이 목록은 실행 환경의 SBOM이나 모든 외부 라이선스 전문을 대신하지 않습니다.
CUDA 선택 설치 이후 실제 버전은 `uvw pip list`로 확인하세요.

## 직접 의존성

| 라이브러리 | 선언 범위 | 역할 |
|---|---|---|
| devmrko-python-foundation | 포함된 0.1.0 | 트랜잭션·오류·요청 경계 |
| NumPy | >=2,<3 | 음성 샘플 배열·무음 생성 |
| SoundFile | >=0.13,<1 | WAV 읽기·쓰기; libsndfile 사용 |
| filelock | >=3.18,<4 | 단일 worker OS 잠금 |
| qwen-tts | ==0.1.1, `tts` extra | Qwen3-TTS 참조 음성 복제 |

## Foundation에서 제공하는 실행 의존성

| 라이브러리 | 범위 | OwnVoice에서의 사용 |
|---|---|---|
| FastAPI | >=0.115,<1 | HTTP API, 요청 DTO |
| Uvicorn | >=0.34,<1 | ASGI 서버 |
| SQLAlchemy | >=2.0.38,<2.1 | SQLite 저장소·세션 |
| pydantic-settings | >=2.7,<3 | 환경변수 설정; Pydantic DTO와 함께 사용 |
| python-multipart | >=0.0.20,<1 | 음성 파일 업로드 |
| HTTPX | >=0.28,<1 | 테스트 클라이언트 및 foundation HTTP 기능 |
| Alembic, Jinja2, PyJWT[crypto] | foundation pyproject 참조 | foundation 전체 API/예제 의존성. OwnVoice는 마이그레이션·템플릿·JWT 인증을 사용하지 않음 |

foundation의 공개 패키지 계약을 보존하기 위해 전체 라이브러리를 유지합니다.
OwnVoice가 인증을 사용하지 않는다고 해서 foundation의 인증 모듈이나 의존성을 임의로 삭제하지 않습니다.

## TTS의 주요 간접 의존성

| 라이브러리 | 역할 |
|---|---|
| PyTorch / torchaudio | 모델 실행·CUDA/MPS/CPU backend와 오디오 연산 |
| Transformers / Accelerate | 모델·processor 로딩, device 배치 |
| huggingface-hub / safetensors | 모델 다운로드·캐시·가중치 파일 |
| librosa / scipy / soxr | 음성 신호 처리 |
| tokenizers | 텍스트 tokenizer |
| Gradio 등 | qwen-tts가 요구하는 패키지; OwnVoice UI는 이를 사용하지 않음 |

큰 간접 의존성은 상위 qwen-tts 패키지 계약 때문에 설치됩니다. OwnVoice 화면 자체는
브라우저 기본 HTML/CSS/JavaScript이며 React·Node.js·npm·번역 프레임워크를 설치할 필요가 없습니다.
i18n은 버전 관리되는 ko/en JSON 카탈로그와 소규모 로더로 구현했습니다.

## 외부 프로그램·개발 도구

- FFmpeg: 참조 파일 변환과 `atempo` 시간 맞춤. Python 패키지 설치와 별도입니다.
- SoX: Qwen 관련 선택 기능의 도구. 현재 12Hz Base 경로는 없어도 동작하지만 import 경고가 날 수 있습니다.
- SQLite: Python 내장 DB; 별도 DB 서버 불필요.
- uv 0.10.6 / Python 3.12: 첫 실행기가 프로젝트 내부에 준비하는 도구.
- pytest, Ruff, mypy: 테스트·정적 검사. Hatchling: wheel/sdist 빌드.
- Qwen3-TTS Base 모델: 외부 Hugging Face 캐시에 저장; 소스 배포물에 포함하지 않음.

OwnVoice와 포함한 작성자 소유 foundation은 MIT입니다. 모델과 외부 패키지는 각각의 라이선스가
적용됩니다. 모델은 [Qwen 공식 모델 카드](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-Base)를 확인하세요.
