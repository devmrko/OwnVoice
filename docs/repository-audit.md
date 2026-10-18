# 공개 저장소 구성 점검

## 제외되는 파일

사용자 `.data/`, DB와 보조 파일, 녹음·생성 오디오, 모델 가중치, `.env`, `.venv`,
`.tools`, 테스트 캐시, 빌드 출력은 `.gitignore`로 제외합니다. 사용자 데이터를 예시로 배포하지 않습니다.
Hugging Face 모델은 첫 사용 시 별도로 받습니다.

## 정리한 항목

포함한 foundation의 중복 `uv.lock`(약 212 KB), Python이 먼저 필요하던 `uvw`, 중첩 GitHub
workflow를 제거했습니다. OwnVoice root의 잠금 파일·첫 실행기·CI 한 곳에서 설치와 검증을 관리합니다.
참조 소스 자체를 다시 내려받도록 바꾸거나 Git submodule로 바꾸지 않았습니다.

## 유지한 항목과 이유

- foundation 라이브러리·템플릿: OwnVoice 의존성 및 라이브러리 공개 API입니다.
- foundation 예제·테스트·설계 문서: 소스 이해와 검증을 위한 참조입니다. OwnVoice 프로세스로 실행되지 않습니다.
- OwnVoice 테스트·wheel 검증 스크립트·CI: 새 체크아웃과 배포 패키지를 확인합니다.
- root uv.lock: 플랫폼별 간접 의존성과 해시를 고정합니다.
- docs: 저장·복구·아키텍처·명세의 원본 문서입니다.

foundation의 Alembic/Jinja2/JWT, qwen-tts의 Gradio처럼 OwnVoice가 직접 호출하지 않는
패키지가 있습니다. 상위 패키지가 선언한 의존성을 임의로 삭제하면 해당 패키지 계약을 깨므로
유지했습니다. 상세 역할은 [라이브러리 명세](libraries.md)에 구분했습니다.
