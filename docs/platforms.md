# 설치·플랫폼 지원

Git이 없어도 GitHub의 **Code → Download ZIP**으로 받아 압축을 풀면 됩니다.

## Python·uv가 없는 첫 실행

- Windows: `start.cmd` 실행. 터미널에서는 `start.cmd -Cuda`로 NVIDIA를 선택합니다.
- macOS·Linux: 프로젝트 폴더에서 `sh start.sh` 실행.
- 설치만: `start.cmd -SetupOnly` 또는 `sh start.sh --setup-only`.

실행 파일은 고정 버전 uv 0.10.6의 공식 설치 프로그램을 HTTPS로 받고,
`.tools/uv`에 설치합니다. uv는 Python 3.12를 `.tools/python`에 준비한 뒤
`.venv`에 실행 패키지를 설치합니다. pytest·Ruff·mypy 같은 개발 도구는 첫 실행기가 설치하지 않습니다. 전역 Python과 PATH를 변경하지 않습니다.
첫 실행에는 인터넷과 쓰기 가능한 프로젝트 디렉터리가 필요합니다.
패키지 설치와 모델 다운로드는 별개입니다. 모델은 첫 합성에서 자동으로 받습니다.

FFmpeg는 별도 도구입니다. 없으면 실행기가 설치 방법을 표시하고 중단합니다.
관리자 권한이나 시스템 패키지 설치를 실행기가 자동으로 수행하지 않습니다.

| 플랫폼 | FFmpeg 준비 |
|---|---|
| Windows 10/11 x64 | `winget install --id Gyan.FFmpeg --exact`; 새 터미널을 열어 PATH 반영 |
| macOS | Homebrew 설치 후 `brew install ffmpeg` |
| Ubuntu/Debian | `sudo apt-get install ffmpeg libsndfile1` |

macOS/Linux의 bootstrap에는 `sh`, `curl`이 필요합니다. Windows는 기본 PowerShell을 사용합니다.
다운로드 실패 시 같은 명령을 다시 실행하세요. 실패한 설치는 모델이 준비됐다고 표시하지 않습니다.

## Windows + NVIDIA CUDA

PyTorch는 [Windows CUDA 설치](https://pytorch.org/get-started/locally/)를 지원합니다.
OwnVoice는 CUDA → MPS → CPU 순서로 사용할 수 있는 장치를 선택합니다.
다만 PyPI의 Windows PyTorch가 CPU 빌드일 수 있어 장치 감지와 패키지 설치를 구분해야 합니다.

```powershell
# NVIDIA 드라이버 설치 후 확인
nvidia-smi
# 설치부터 서버 실행까지. Python·uv 사전 설치 불필요.
.\start.cmd -Cuda
```

`-Cuda`는 기본 잠금 파일 설치 후 `uv pip --torch-backend=auto`로 드라이버에 맞는
PyTorch/torchaudio를 선택하고 `torch.cuda.is_available()`을 확인합니다.
CUDA가 사용 불가능하면 CPU로 조용히 넘어가지 않고 오류로 중단합니다.
이 선택은 torch 계열 패키지 버전을 root uv.lock과 다르게 만들 수 있습니다.
따라서 이후에도 같은 실행기와 `-Cuda`를 사용하세요. 일반 `uv sync`는 원래 잠금 버전으로 되돌립니다.
[uv의 자동 backend 선택](https://docs.astral.sh/uv/guides/integration/pytorch/#automatic-backend-selection)은
`uv pip`에만 적용되며 `uv sync`의 장치 자동 선택 기능이 아닙니다.

FlashAttention은 필요하지 않습니다. eager attention을 사용합니다.
CUDA에서는 지원되면 bfloat16, 그렇지 않으면 float32를 사용합니다.
모델 메모리 부족·드라이버 불일치·음질은 장치 이름만으로 판단할 수 없습니다.
현재 프로젝트 검증은 Windows CPU CI와 CUDA 감지 테스트까지이며, Windows NVIDIA에서
모델 다운로드 후 실제 음성 합성·음질·성능은 실기기 검증이 필요합니다.

## 환경변수와 수동 명령

```powershell
$env:OWNVOICE_DATA_DIR = 'D:\OwnVoiceData'
$env:OWNVOICE_DEVICE = 'cuda'
# 첫 실행 도구 준비 후 사용
.\uvw.ps1 run --no-sync ownvoice doctor
.\uvw.ps1 run --no-sync ownvoice download-model
.\uvw.ps1 run --no-sync ownvoice download-model --offline
```

PowerShell 실행 정책이 파일 실행을 막으면 `powershell -NoProfile -ExecutionPolicy Bypass -File .\uvw.ps1 ...`을
사용합니다. 이는 해당 프로세스에만 적용되며 머신 실행 정책을 변경하지 않습니다.

macOS/Linux에서는 `./uvw`를 사용하고 `export OWNVOICE_DATA_DIR=/absolute/path`처럼 설정합니다.
웹과 worker에 같은 환경을 적용해야 합니다. `start`는 둘을 함께 관리합니다.
브라우저를 닫아도 작업은 계속되며 Ctrl+C로 종료합니다. 강제 종료 시 다음 실행에서 복구합니다.

## 지원 수준

| 조합 | 검증 범위 |
|---|---|
| macOS Apple Silicon/MPS | 실제 합성 확인, UI·종료·복구 테스트 |
| Linux CPU | CI 설치·API·오디오·패키징 테스트 |
| Windows CPU | CI 설치·API·오디오·패키징 및 bootstrap 테스트 |
| Windows/Linux NVIDIA CUDA | 코드 경로·감지 테스트; 실제 GPU 추론 미검증 |

CI는 모델 가중치나 사용자의 음성을 사용하지 않습니다. CPU CI 통과를 CUDA 실측 결과로 보지 않습니다.
