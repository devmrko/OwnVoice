import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator
from python_foundation.errors import BusinessError, ErrorCategory, ErrorSpec


def invalid(message: str) -> BusinessError:
    return BusinessError(ErrorSpec("INVALID_INPUT", ErrorCategory.VALIDATION, message))


class Segment(BaseModel):
    index: int
    start_ms: int | None = None
    end_ms: int | None = None
    original: str
    text: str
    status: str = "pending"
    duration_ms: int | None = None
    speed: float = 1.0
    synthesis_attempts: int = 0
    timing_error: str | None = None


class JobRequest(BaseModel):
    engine: Literal["qwen", "qwen-small", "chatterbox"] = "qwen"
    profile_id: str
    mode: Literal["text", "srt"]
    content: str = Field(min_length=1, max_length=100_000)
    language: Literal["Korean", "English", "Japanese", "Chinese", "Auto"] = "Korean"

    @field_validator("content")
    @classmethod
    def nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Text is empty")
        return value


class SegmentEdit(BaseModel):
    text: str = Field(min_length=1, max_length=1000)

    @field_validator("text")
    @classmethod
    def nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Text is empty")
        return value.strip()


TIMING = re.compile(r"^(\d{2,}):([0-5]\d):([0-5]\d),(\d{3}) --> (\d{2,}):([0-5]\d):([0-5]\d),(\d{3})$")


def parse_segments(mode: str, content: str) -> list[Segment]:
    if mode == "text":
        parts = [p.strip() for p in re.split(r"(?<=[.!?。！？])\s+|\n+", content) if p.strip()]
        if not parts or any(len(p) > 1000 for p in parts) or len(parts) > 500:
            raise invalid("문장을 1,000자 이내로 나누고 500개 이하로 입력해 주세요.")
        return [Segment(index=i, original=p, text=p) for i, p in enumerate(parts)]
    blocks = re.split(r"\n\s*\n", content.lstrip("\ufeff").replace("\r\n", "\n").strip())
    result: list[Segment] = []
    previous_end = 0
    for i, block in enumerate(blocks):
        lines = block.splitlines()
        if len(lines) < 3 or not lines[0].strip().isdigit():
            raise invalid(f"SRT {i + 1}번 구간 형식을 확인해 주세요.")
        match = TIMING.fullmatch(lines[1].strip())
        if match is None:
            raise invalid(f"SRT {i + 1}번 시간 형식이 잘못되었습니다.")
        values = list(map(int, match.groups()))
        start, end = [
            ((values[j] * 60 + values[j + 1]) * 60 + values[j + 2]) * 1000 + values[j + 3] for j in (0, 4)
        ]
        text = " ".join(line.strip() for line in lines[2:]).strip()
        if start < previous_end or end <= start or end > 7_200_000:
            raise invalid("자막은 겹치지 않는 시간순이어야 하며 전체 길이는 2시간 이내여야 합니다.")
        if not text or len(text) > 1000 or len(result) >= 500:
            raise invalid("자막은 구간당 1~1,000자, 전체 500개 이하여야 합니다.")
        result.append(Segment(index=i, start_ms=start, end_ms=end, original=text, text=text))
        previous_end = end
    return result
