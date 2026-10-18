# 데이터 저장·백업·복구

기본 데이터 디렉터리는 실행한 디렉터리의 `.data/`입니다. 다른 위치에서 실행한다면
`OWNVOICE_DATA_DIR`에 절대 경로를 지정하고 웹과 worker에 같은 값을 사용하세요.
`start.sh`와 `start.cmd`는 항상 프로젝트 디렉터리에서 시작합니다.

## 파일 구조

```text
.data/
  ownvoice.db                    # SQLite: 목소리 정보, 작업 내역, 구간 상태
  ownvoice.db-wal / -shm          # SQLite가 생성할 수 있는 보조 파일
  worker.lock                    # 동일 데이터에 worker 1개만 허용하는 OS 잠금
  worker.json                    # PID, 마지막 heartbeat, 합성 검증 여부
  worker.tmp                     # heartbeat 교체 중에만 사용하는 파일
  profiles/<profile UUID>/
    reference.wav                # 변환된 참조 음성: mono, 24 kHz
    upload                       # 업로드 변환 중 임시 파일; 정상 변환 후 제거
  jobs/<job UUID>/
    0.wav, 1.wav, ...             # 0부터 시작하는 구간별 원본 합성/최단 후보
    0.fit.wav, ...                # FFmpeg로 속도를 조정한 중간 결과
    0.tmp.wav, ...                # 원자적 파일 교체 전 임시 WAV
    output.tmp.wav               # 전체 타임라인 조립 중 임시 파일
    output.wav                   # 모든 구간 완료 후 제공되는 최종 WAV
```

`diagnostics/`는 개발 중 수동 진단으로 만들어질 수 있으며 앱 필수 데이터가 아닙니다.
완성 파일이 디스크에 있더라도 작업 상태가 `completed`가 아니면 다운로드 API는 거부합니다.
재생성 시 예전 output.wav가 남을 수 있으므로 파일 존재만으로 완료 여부를 판단하지 마세요.

## 작업 내역은 어디에 있는가

`ownvoice.db`의 `records` 테이블 하나를 사용합니다.

| 컬럼 | 의미 |
|---|---|
| `id` | UUID, 기본 키 |
| `kind` | `profile` 또는 `job` |
| `created_at` | UTC ISO-8601 생성 시각 |
| `data` | JSON; 목소리 또는 작업 데이터 |

목소리 JSON에는 이름과 참조 대본이 들어갑니다. 작업 JSON에는 목소리 ID/이름,
입력 원문(`content`), 입력 모드, 합성 언어, 작업 상태, 구간별 텍스트와 원문, SRT 시작·종료 밀리초,
합성 길이·가속 배율·시도 횟수·오류, 실행 시간과 측정 기록이 들어갑니다.
입력한 SRT를 별도 `.srt` 파일로 보관하지 않습니다. 파싱한 구간 데이터가 기준이며,
SRT 번호는 내부에서 0부터 시작하는 연속 인덱스로 바뀝니다.
화면 표시용 진행률은 조회 시 계산하고 DB에는 별도로 저장하지 않습니다.

읽기 전용 확인 예시 (앱의 Python 환경 사용):

```sh
uv run --no-sync python -c "import sqlite3; c=sqlite3.connect('file:.data/ownvoice.db?mode=ro', uri=True); print(c.execute('select kind,count(*) from records group by kind').fetchall())"
```

직접 SQL로 상태를 바꾸지 마세요. API의 편집·재시도는 관련 구간 캐시도 함께 관리합니다.

## 백업과 복구

1. `start`를 실행한 터미널에서 Ctrl+C로 종료합니다. 별도 실행했다면 웹과 worker 모두 종료합니다.
2. `.data/` 전체를 복사합니다. DB만 복사하면 목소리와 오디오가 빠집니다.
3. 새 설치의 같은 데이터 경로에 전체 폴더를 복원합니다.
4. 같은 모델 설정으로 실행합니다. worker는 중단된 `running` 작업을 다시 대기열에 넣습니다.
5. 완료된 구간은 재사용하고 미완료 구간은 남은 시도 횟수 내에서 처리합니다.

강제 종료 후 `worker.json`이 남아도 실제 OS 잠금은 프로세스 종료 시 해제됩니다.
heartbeat는 20초가 지나면 연결 끊김으로 판단합니다. 실행 중에 `worker.lock`을 삭제하지 마세요.
전체 작업 삭제·프로필 삭제 UI와 스키마 마이그레이션 체계는 아직 제공하지 않습니다.
업데이트 전에는 백업을 보관하세요.

## 코드·모델·도구·브라우저 저장소

| 위치 | 내용 | GitHub 포함 |
|---|---|---|
| `.data/` | 사용자 목소리·대본·작업·WAV | 제외 |
| `.venv/` | Python 패키지 실행 환경 | 제외 |
| `.tools/uv/`, `.tools/python/` | 첫 실행 도구가 설치한 uv·Python | 제외 |
| Hugging Face 캐시 | 모델 가중치·tokenizer; 기본 `~/.cache/huggingface`, `HF_HOME`으로 변경 | 제외 |
| 브라우저 localStorage `ownvoice.locale` | `ko` 또는 `en` 화면 언어 | 서버와 무관 |
| 브라우저 메모리 | 저장하지 않은 편집·녹음 미리보기 | 새로고침하면 소실 |

음성·대본은 로컬에 저장됩니다. 패키지/모델을 받는 동안 외부 서버와 통신합니다.
화면 언어를 바꿔도 저장된 대본·합성 언어·WAV는 바뀌지 않습니다.
