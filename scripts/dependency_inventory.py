"""Generate the lockfile inventory; no installed packages or credentials needed."""

import argparse
import tomllib
from pathlib import Path

root = Path(__file__).resolve().parents[1]
lock = tomllib.loads((root / "uv.lock").read_text(encoding="utf-8"))
lines = [
    "# 잠금 파일 패키지 목록",
    "",
    "uv.lock 기준 전체 플랫폼·선택 의존성의 합집합입니다. 모든 패키지가 항상 설치되지는 않습니다.",
    "CUDA 실행기의 torch 재선택은 이 목록과 달라질 수 있습니다. `uvw pip list`로 실제 환경을 확인하세요.",
    "재생성: `uv run python scripts/dependency_inventory.py`",
    "",
    "| 패키지 | 잠금 버전 | 출처 |",
    "|---|---|---|",
]
for package in sorted(lock["package"], key=lambda p: (p["name"], p["version"])):
    source = package["source"]
    location = "PyPI" if "registry" in source else source.get("directory", source.get("editable", "local"))
    lines.append(f"| {package['name']} | {package['version']} | {location} |")
text = "\n".join(lines) + "\n"
target = root / "docs/dependencies-lock.md"
parser = argparse.ArgumentParser()
parser.add_argument("--check", action="store_true")
if parser.parse_args().check:
    if not target.exists() or target.read_text(encoding="utf-8") != text:
        raise SystemExit("Regenerate docs/dependencies-lock.md")
else:
    target.write_text(text, encoding="utf-8")
