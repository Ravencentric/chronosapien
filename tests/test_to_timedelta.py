from collections.abc import Callable
from datetime import date, timedelta

import pytest

from chronosapien import (
    CalendarUnitError,
    ChronosapienError,
    Duration,
    SpanParseError,
    to_timedelta,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2 hours, 30 minutes", timedelta(hours=2, minutes=30)),
        ("PT2H30M", timedelta(hours=2, minutes=30)),
        ("1w 2d 3h", timedelta(days=9, hours=3)),
        ("P0Y0M1D", timedelta(days=1)),
        ("1999ns", timedelta(microseconds=1)),
        ("1999ns ago", timedelta(microseconds=-1)),
    ],
)
def test_to_timedelta(text: str, expected: timedelta) -> None:
    assert to_timedelta(text) == expected


@pytest.mark.parametrize("text", ["1 year", "P1M"])
def test_to_timedelta_requires_a_calendar_reference(text: str) -> None:
    with pytest.raises(CalendarUnitError) as error:
        _ = to_timedelta(text)
    assert isinstance(error.value, ChronosapienError)
    assert str(error.value) == (
        "relative_to is required for years or months. Pass a date or datetime."
    )


@pytest.mark.parametrize("parse", [to_timedelta, Duration])
def test_invalid_text_raises_span_parse_error(
    parse: Callable[[str], timedelta | Duration],
) -> None:
    with pytest.raises(SpanParseError) as error:
        _ = parse("tomorrow")
    assert isinstance(error.value, ChronosapienError)


def test_to_timedelta_matches_duration_conversion() -> None:
    start = date(2026, 2, 1)
    elapsed = Duration("1mo").to_timedelta(relative_to=start)
    assert to_timedelta("1mo", relative_to=start) == elapsed
