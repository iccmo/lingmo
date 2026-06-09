import pytest
from fastapi import HTTPException

from novel_writer.routers.novel.request_validation import bounded_float, bounded_int, text_field


def test_bounded_float_rejects_non_finite_values():
    with pytest.raises(HTTPException) as exc:
        bounded_float(
            {"quality_threshold": "nan"},
            "quality_threshold",
            0.8,
            0.5,
            1.0,
            status_code=422,
            invalid_detail="invalid",
            range_detail="out of range",
        )

    assert exc.value.status_code == 422
    assert exc.value.detail == "out of range"


def test_bounded_int_uses_configured_error_message():
    with pytest.raises(HTTPException) as exc:
        bounded_int(
            {"chapters": "很多"},
            "chapters",
            10,
            1,
            20,
            status_code=400,
            invalid_detail="chapters must be an integer",
            range_detail="chapters must be 1-20",
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "chapters must be an integer"


def test_bounded_int_accepts_valid_numeric_string():
    assert bounded_int(
        {"chapters": "12"},
        "chapters",
        10,
        1,
        20,
        status_code=400,
        invalid_detail="invalid",
        range_detail="range",
    ) == 12


def test_text_field_coerces_scalar_and_handles_none():
    assert text_field({"direction": 123}, "direction") == "123"
    assert text_field({"direction": None}, "direction", "L1") == "L1"
    assert text_field({}, "direction", "L1") == "L1"
