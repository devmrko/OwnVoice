"""Translate presentation fields without changing stored jobs or user text."""

import json
import re
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any


@lru_cache(maxsize=1)
def english() -> dict[str, str]:
    data: dict[str, str] = json.loads(
        (Path(__file__).parent / "static/locales/en.json").read_text(encoding="utf-8")
    )
    return data


def language(header: str = "ko") -> str:
    choices = []
    for item in header.lower().split(","):
        parts = item.strip().split(";")
        code = parts[0].split("-")[0]
        try:
            quality = float(parts[1].strip().removeprefix("q=")) if len(parts) > 1 else 1.0
        except ValueError:
            continue
        if code in ("ko", "en") and 0 < quality <= 1:
            choices.append((quality, code))
    return max(choices, key=lambda choice: choice[0])[1] if choices else "ko"


def translate(message: str | None, locale: str) -> str | None:
    if message is None or locale != "en":
        return message
    catalog = english()
    if message in catalog:
        return catalog[message]
    # Older jobs stored rendered Korean errors. Translate known templates only.
    for source, target in catalog.items():
        if "{0}" not in source:
            continue
        parts = re.split(r"\{\d+\}", source)
        pattern = "(.+?)".join(re.escape(part) for part in parts)
        match = re.fullmatch(pattern, message)
        if match:
            return target.format(*match.groups())
    return message


def localize_job(job: dict[str, Any], locale: str) -> dict[str, Any]:
    result = deepcopy(job)
    result["error"] = translate(result.get("error"), locale)
    for segment in result.get("segments", []):
        segment["timing_error"] = translate(segment.get("timing_error"), locale)
    return result
