"""Small request validation helpers for legacy dict-based routes."""

from __future__ import annotations

import math
from typing import NoReturn

from fastapi import HTTPException


def _raise(status_code: int, detail: str) -> NoReturn:
    raise HTTPException(status_code, detail=detail)


def text_field(data: dict, key: str, default: str = "") -> str:
    value = data.get(key, default)
    if value is None:
        return default
    return str(value).strip()


def bounded_int(
    data: dict,
    key: str,
    default: int,
    lower: int,
    upper: int,
    *,
    status_code: int,
    invalid_detail: str,
    range_detail: str,
) -> int:
    raw = data.get(key, default)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        _raise(status_code, invalid_detail)
    if value < lower or value > upper:
        _raise(status_code, range_detail)
    return value


def bounded_float(
    data: dict,
    key: str,
    default: float,
    lower: float,
    upper: float,
    *,
    status_code: int,
    invalid_detail: str,
    range_detail: str,
) -> float:
    raw = data.get(key, default)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        _raise(status_code, invalid_detail)
    if not math.isfinite(value) or value < lower or value > upper:
        _raise(status_code, range_detail)
    return value
