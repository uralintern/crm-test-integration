"""Мелкие помощники движка: приведение типов, нормализация текста, отпечатки."""

import hashlib
import json
from typing import Any


def to_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def normalized_text(value: Any) -> str:
    return str(value or "").strip()


def lower_text(value: Any) -> str:
    return normalized_text(value).lower()


def stable_fingerprint(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
