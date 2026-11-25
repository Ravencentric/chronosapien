from datetime import date, datetime, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pytest

from chronosapien import CalendarSpan, CalendarUnitError, InvalidUnitError, duration


def test_span_preserves_signed_components() -> None:
    span = CalendarSpan(
        "1 year, 2 months, 3 weeks, 4 days, "
        "5 hours, 90 minutes, 7 seconds, 8ms, 9us, 10ns ago"
    )

    assert span.years == -1
    assert span.months == -2
    assert span.weeks == -3
    assert span.days == -4
    assert span.hours == -5
    assert span.minutes == -90
    assert span.seconds == -7
    assert span.milliseconds == -8
    assert span.microseconds == -9
    assert span.nanoseconds == -10


def test_span_formats() -> None:
    span = CalendarSpan("P1M2DT3H")

    assert str(span) == "P1M2DT3H"
    assert span.to_friendly() == "1mo 2d 3h"
    assert repr(span) == "CalendarSpan('1mo 2d 3h')"


def test_span_equality_and_hash_use_stored_units() -> None:
    one_hour = CalendarSpan("1h")
    iso_hour = CalendarSpan("PT1H")

    assert one_hour == iso_hour
    assert hash(one_hour) == hash(iso_hour)
    assert one_hour != CalendarSpan("60m")
    assert one_hour.minutes == 0


def test_month_duration_accounts_for_leap_year() -> None:
    month = CalendarSpan("1mo")

    assert month.to_timedelta(relative_to=date(2024, 2, 1)) == timedelta(days=29)
    assert month.to_timedelta(relative_to=date(2025, 2, 1)) == timedelta(days=28)


def test_month_equivalence_depends_on_reference_date() -> None:
    month = CalendarSpan("1mo")
    twenty_eight_days = CalendarSpan("28d")

    assert month.equivalent_to(twenty_eight_days, relative_to=date(2025, 2, 1))
    assert not month.equivalent_to(twenty_eight_days, relative_to=date(2024, 2, 1))


@pytest.mark.parametrize("relative_to", [None, date(2025, 2, 1)])
def test_equivalence_uses_nanosecond_precision(relative_to: date | None) -> None:
    assert not CalendarSpan("1ns").equivalent_to(
        CalendarSpan("2ns"), relative_to=relative_to
    )


@pytest.mark.parametrize(("text", "hours"), [("1d", 24), ("1w", 168)])
def test_days_and_weeks_are_fixed_without_a_reference(text: str, hours: int) -> None:
    span = CalendarSpan(text)

    assert span.to_timedelta() == timedelta(hours=hours)
    assert span.total("hour", relative_to=None) == hours
    assert span.equivalent_to(CalendarSpan(f"{hours}h"))


@pytest.mark.parametrize("text", ["1mo", "1y"])
def test_months_and_years_require_a_reference(text: str) -> None:
    span = CalendarSpan(text)
    hour = CalendarSpan("1h")
    expected = "relative_to is required for years or months. Pass a date or datetime."

    with pytest.raises(CalendarUnitError) as error:
        _ = span.to_timedelta()
    assert str(error.value) == expected

    with pytest.raises(CalendarUnitError) as error:
        _ = hour.equivalent_to(span)
    assert str(error.value) == expected

    with pytest.raises(CalendarUnitError) as error:
        _ = span.total("hour")
    assert str(error.value) == expected


def test_total_requires_a_reference_for_months() -> None:
    with pytest.raises(CalendarUnitError) as error:
        _ = CalendarSpan("24h").total("month")
    assert str(error.value) == (
        "relative_to is required for years or months. Pass a date or datetime."
    )


def test_total_treats_weeks_as_seven_days_without_a_reference() -> None:
    assert CalendarSpan("252h").total("week", relative_to=None) == 1.5


def test_total_rejects_an_unknown_unit() -> None:
    with pytest.raises(InvalidUnitError) as error:
        _ = CalendarSpan("1h").total("fortnight")  # pyrefly: ignore[bad-argument-type]
    assert str(error.value) == 'unknown unit: "fortnight"'


def test_total_preserves_fractional_microseconds() -> None:
    assert CalendarSpan("-1500ns").total("microsecond") == -1.5


@pytest.mark.parametrize(
    "zone",
    [None, timezone(timedelta(hours=5, minutes=30))],
    ids=["naive", "fixed-offset"],
)
def test_month_arithmetic_clamps_to_end_of_february(zone: tzinfo | None) -> None:
    month = CalendarSpan("1mo")
    january_31 = datetime(2024, 1, 31, 9, tzinfo=zone)
    march_31 = datetime(2024, 3, 31, 9, tzinfo=zone)
    february_29 = datetime(2024, 2, 29, 9, tzinfo=zone)

    added = month.add_to(january_31)
    assert added == february_29
    assert added.tzinfo == zone

    subtracted = month.subtract_from(march_31)
    assert subtracted == february_29
    assert subtracted.tzinfo == zone

    assert month.to_timedelta(relative_to=january_31) == timedelta(days=29)


def test_spring_dst_transition_makes_calendar_day_23_hours() -> None:
    try:
        zone = ZoneInfo("America/New_York")
    except ZoneInfoNotFoundError:
        pytest.skip("America/New_York time zone data is unavailable")

    midnight_before = datetime(2024, 3, 10, tzinfo=zone)
    midnight_after = datetime(2024, 3, 11, tzinfo=zone)
    calendar_day = CalendarSpan("1d")

    assert calendar_day.to_timedelta(relative_to=midnight_before) == timedelta(hours=23)
    assert calendar_day.equivalent_to(CalendarSpan("23h"), relative_to=midnight_before)
    assert calendar_day.total("hour", relative_to=midnight_before) == 23.0
    assert CalendarSpan("23h").total("day", relative_to=midnight_before) == 1.0
    assert duration("1d", relative_to=midnight_before) == timedelta(hours=23)
    assert duration("1d", relative_to=None) == timedelta(hours=24)

    added = calendar_day.add_to(midnight_before)
    assert added == midnight_after
    assert added.tzinfo == zone

    subtracted = calendar_day.subtract_from(midnight_after)
    assert subtracted == midnight_before
    assert subtracted.tzinfo == zone


def test_unsupported_timezone_raises_type_error() -> None:
    start = datetime(2024, 3, 10, tzinfo=tzinfo())

    with pytest.raises(TypeError, match="naive datetime"):
        _ = CalendarSpan("1d").to_timedelta(relative_to=start)


def test_span_sign_predicates() -> None:
    assert CalendarSpan("2h").is_positive()
    assert CalendarSpan("-2h").is_negative()

    zero = CalendarSpan("0s")
    assert zero.is_zero()
    assert not zero.is_positive()
    assert not zero.is_negative()


def test_abs_and_negate() -> None:
    positive = CalendarSpan("2h")
    negative = CalendarSpan("-2h")

    assert negative.abs() == positive
    assert positive.negate() == negative


def test_scaling_keeps_original_units() -> None:
    span = CalendarSpan("50m")

    assert span.scale(-2) == CalendarSpan("-100m")
    assert span.scale(0) == CalendarSpan("0s")


@pytest.mark.parametrize(
    "factor",
    [
        pytest.param(100_000, id="scaled-years-out-of-range"),
        pytest.param(2**63, id="factor-out-of-range"),
    ],
)
def test_scale_overflow(factor: int) -> None:
    with pytest.raises(OverflowError):
        _ = CalendarSpan("1y").scale(factor)
