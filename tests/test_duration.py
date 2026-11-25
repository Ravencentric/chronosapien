from collections.abc import Callable
from datetime import timedelta

import pytest

from chronosapien import (
    CalendarSpan,
    CalendarUnitError,
    ChronosapienError,
    SpanParseError,
    duration,
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
def test_duration(text: str, expected: timedelta) -> None:
    assert duration(text) == expected


@pytest.mark.parametrize("text", ["1 year", "P1M"])
def test_duration_rejects_calendar_units(text: str) -> None:
    with pytest.raises(CalendarUnitError) as error:
        _ = duration(text)
    assert isinstance(error.value, ChronosapienError)


@pytest.mark.parametrize("parse", [duration, CalendarSpan])
def test_invalid_text_raises_span_parse_error(
    parse: Callable[[str], timedelta | CalendarSpan],
) -> None:
    with pytest.raises(SpanParseError) as error:
        _ = parse("tomorrow")
    assert isinstance(error.value, ChronosapienError)
