from datetime import UTC, date, datetime, timedelta, timezone, tzinfo
from enum import IntEnum
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pytest

from chronosapien import (
    CalendarUnitError,
    ChronosapienError,
    Duration,
    DurationFormatError,
    DurationFormatter,
    DurationRoundError,
    InvalidUnitError,
    Ordering,
    to_timedelta,
)


def test_span_preserves_signed_components() -> None:
    span = Duration(
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
    span = Duration("P1M2DT3H")

    assert str(span) == "P1M2DT3H"
    assert span.to_friendly() == "1mo 2d 3h"
    assert span.to_friendly(designator="compact") == "1mo 2d 3h"
    assert repr(span) == "Duration('1mo 2d 3h')"


def test_verbose_friendly_output_round_trips() -> None:
    span = Duration("1h 30m ago")

    text = span.to_friendly(designator="verbose", spacing="designators", comma=True)

    assert text == "1 hour, 30 minutes ago"
    assert Duration(text) == span


def test_friendly_output_can_override_commas() -> None:
    span = Duration("1h 30m")

    assert span.to_friendly(comma=None) == "1h 30m"
    assert span.to_friendly(comma=True) == "1h, 30m"
    assert span.to_friendly(designator="verbose", comma=False) == "1hour 30minutes"
    assert Duration("1y 2mo").to_friendly(designator="short", comma=True) == "1yr, 2mos"


def test_friendly_output_can_override_spacing() -> None:
    span = Duration("1h 30m")

    assert span.to_friendly(spacing="none") == "1h30m"
    assert span.to_friendly(spacing="none", comma=True) == "1h,30m"
    assert span.to_friendly(designator="verbose") == "1hour 30minutes"
    assert span.to_friendly(designator="verbose", spacing="designators") == (
        "1 hour 30 minutes"
    )


def test_friendly_direction_can_override_the_sign() -> None:
    span = Duration("-1d 2h")

    assert span.to_friendly(hhmmss=True) == "1d 02:00:00 ago"
    assert span.to_friendly(hhmmss=True, direction="auto") == "1d 02:00:00 ago"
    assert span.to_friendly(hhmmss=True, direction="sign") == "-1d 02:00:00"
    assert span.to_friendly(direction="sign") == "-1d 2h"
    assert span.to_friendly(spacing="none", direction="suffix") == "1d2h ago"


def test_hhmmss_preserves_stored_minutes() -> None:
    span = Duration("1mo 2d 1500m 1501ms 1ns ago")

    text = span.to_friendly(hhmmss=True)
    assert text == "1mo 2d 00:1500:01.501000001 ago"


def test_hhmmss_with_zero_time_fields() -> None:
    assert Duration("0s").to_friendly(hhmmss=True) == "00:00:00"
    assert Duration("-1d").to_friendly(hhmmss=True) == "1d 00:00:00 ago"


def test_hhmmss_combines_with_designator_and_comma() -> None:
    span = Duration("1d 2h")

    assert span.to_friendly(designator="verbose", hhmmss=True) == "1day 02:00:00"
    assert span.to_friendly(comma=True, hhmmss=True) == "1d, 02:00:00"
    text = Duration("1y 2mo 2h").to_friendly(spacing="none", hhmmss=True)
    assert text == "1y2mo 02:00:00"


def test_friendly_precision_truncates_fractional_output() -> None:
    span = Duration("1259ms")

    assert span.to_friendly(precision=2) == "1259ms"
    assert span.to_friendly(fractional="second", precision=2) == "1.25s"
    assert span.to_friendly(hhmmss=True, precision=0) == "00:00:01"
    assert span.to_friendly(hhmmss=True, fractional="second") == "00:00:01.259"


def test_friendly_padding_applies_to_integer_fields() -> None:
    span = Duration("1d 2h")

    assert span.to_friendly(padding=3) == "001d 002h"
    assert span.to_friendly(hhmmss=True, padding=3) == "001d 002:000:000"
    assert span.to_friendly(hhmmss=True, padding=0) == "1d 2:0:0"


def test_friendly_numeric_options_accept_the_maximum() -> None:
    span = Duration("1s")

    assert span.to_friendly(fractional="second", precision=9) == "1.000000000s"
    assert DurationFormatter(padding=20).format(span) == "00000000000000000001s"


@pytest.mark.parametrize(
    ("precision", "error"),
    [
        (-1, OverflowError),
        (10, DurationFormatError),
        (255, DurationFormatError),
        (256, OverflowError),
        (2**128, OverflowError),
    ],
)
def test_to_friendly_rejects_out_of_range_precision(
    precision: int, error: type[Exception]
) -> None:
    span = Duration("1s")
    with pytest.raises(error):
        _ = span.to_friendly(precision=precision)


@pytest.mark.parametrize(
    ("padding", "error"),
    [
        (-1, OverflowError),
        (21, DurationFormatError),
        (255, DurationFormatError),
        (256, OverflowError),
        (2**128, OverflowError),
    ],
)
def test_duration_formatter_rejects_out_of_range_padding(
    padding: int, error: type[Exception]
) -> None:
    with pytest.raises(error):
        _ = DurationFormatter(padding=padding)


def test_hhmmss_uses_fractional_seconds() -> None:
    span = Duration("1h 250ms")
    assert span.to_friendly(hhmmss=True, fractional="hour") == "01:00:00.25"


def test_to_friendly_rejects_an_unknown_designator() -> None:
    with pytest.raises(DurationFormatError) as error:
        _ = Duration("1h").to_friendly(designator="long")  # pyrefly: ignore[bad-argument-type]
    assert str(error.value) == 'unknown friendly designator: "long"'


def test_to_friendly_rejects_unknown_spacing() -> None:
    with pytest.raises(DurationFormatError) as error:
        _ = Duration("1h").to_friendly(spacing="all")  # pyrefly: ignore[bad-argument-type]
    assert str(error.value) == 'unknown friendly spacing: "all"'


def test_to_friendly_rejects_unknown_direction() -> None:
    span = Duration("1h")
    with pytest.raises(DurationFormatError) as error:
        _ = span.to_friendly(direction="force_sign")  # pyrefly: ignore[bad-argument-type]
    assert str(error.value) == 'unknown friendly direction: "force_sign"'


def test_to_friendly_rejects_an_unknown_fractional_unit() -> None:
    with pytest.raises(DurationFormatError) as error:
        _ = Duration("1h").to_friendly(fractional="day")  # pyrefly: ignore[bad-argument-type]
    assert str(error.value) == 'unknown fractional unit: "day"'


def test_duration_formatter_reuses_options() -> None:
    formatter = DurationFormatter(
        designator="short",
        spacing="designators",
        comma=True,
        direction="sign",
        hhmmss=True,
        fractional="second",
        precision=3,
        padding=3,
    )
    duration = Duration("-1y 1259ms")

    assert formatter.format(duration) == "-001 yr, 000:000:001.259"
    assert formatter.format(Duration("2h")) == "002:000:000.000"
    assert DurationFormatter().format(duration) == duration.to_friendly()


def test_duration_formatter_is_immutable() -> None:
    formatter = DurationFormatter(precision=3)

    with pytest.raises(AttributeError):
        object.__setattr__(formatter, "precision", 2)


def test_duration_formatter_validates_options_at_construction() -> None:
    with pytest.raises(DurationFormatError) as error:
        _ = DurationFormatter(fractional="day")  # pyrefly: ignore[bad-argument-type]
    assert str(error.value) == 'unknown fractional unit: "day"'


def test_span_equality_and_hash_use_stored_units() -> None:
    one_hour = Duration("1h")
    iso_hour = Duration("PT1H")

    assert one_hour == iso_hour
    assert hash(one_hour) == hash(iso_hour)
    assert one_hour != Duration("60m")
    assert one_hour.minutes == 0


def test_month_duration_accounts_for_leap_year() -> None:
    month = Duration("1mo")

    assert month.to_timedelta(relative_to=date(2024, 2, 1)) == timedelta(days=29)
    assert month.to_timedelta(relative_to=date(2025, 2, 1)) == timedelta(days=28)


def test_month_equivalence_depends_on_reference_date() -> None:
    month = Duration("1mo")
    twenty_eight_days = Duration("28d")

    assert month.equivalent_to(twenty_eight_days, relative_to=date(2025, 2, 1))
    assert not month.equivalent_to(twenty_eight_days, relative_to=date(2024, 2, 1))


@pytest.mark.parametrize("relative_to", [None, date(2025, 2, 1)])
def test_equivalence_uses_nanosecond_precision(relative_to: date | None) -> None:
    assert not Duration("1ns").equivalent_to(Duration("2ns"), relative_to=relative_to)


def test_compare_returns_int_enum_members() -> None:
    assert issubclass(Ordering, IntEnum)
    assert [member.value for member in Ordering] == [-1, 0, 1]

    hour = Duration("1h")
    assert hour.compare(Duration("1h 1ns")) is Ordering.LESS
    assert hour.compare(Duration("60m")) is Ordering.EQUAL
    assert hour.compare(Duration("59m")) is Ordering.GREATER


@pytest.mark.parametrize(("text", "hours"), [("1d", 24), ("1w", 168)])
def test_days_and_weeks_are_fixed_without_a_reference(text: str, hours: int) -> None:
    span = Duration(text)

    assert span.to_timedelta() == timedelta(hours=hours)
    assert span.total("hour", relative_to=None) == hours
    assert span.equivalent_to(Duration(f"{hours}h"))


@pytest.mark.parametrize("text", ["1mo", "1y"])
def test_months_and_years_require_a_reference(text: str) -> None:
    span = Duration(text)
    hour = Duration("1h")
    expected = "relative_to is required for years or months. Pass a date or datetime."

    with pytest.raises(CalendarUnitError) as error:
        _ = span.to_timedelta()
    assert str(error.value) == expected

    with pytest.raises(CalendarUnitError) as error:
        _ = hour.equivalent_to(span)
    assert str(error.value) == expected

    with pytest.raises(CalendarUnitError, match="relative_to is required"):
        _ = hour.compare(span)

    with pytest.raises(CalendarUnitError) as error:
        _ = span.total("hour")
    assert str(error.value) == expected


def test_total_requires_a_reference_for_months() -> None:
    with pytest.raises(CalendarUnitError) as error:
        _ = Duration("24h").total("month")
    assert str(error.value) == (
        "relative_to is required for years or months. Pass a date or datetime."
    )


def test_total_treats_weeks_as_seven_days_without_a_reference() -> None:
    assert Duration("252h").total("week", relative_to=None) == 1.5


def test_total_rejects_an_unknown_unit() -> None:
    with pytest.raises(InvalidUnitError) as error:
        _ = Duration("1h").total("fortnight")  # pyrefly: ignore[bad-argument-type]
    assert str(error.value) == 'unknown unit: "fortnight"'


def test_total_preserves_fractional_microseconds() -> None:
    assert Duration("-1500ns").total("microsecond") == -1.5


def test_round_preserves_nanoseconds_by_default() -> None:
    result = Duration("90m 1ns").round(largest="hour")

    assert result == Duration("1h 30m 1ns")


@pytest.mark.parametrize(("text", "expected"), [("90m", "2h"), ("-90m", "-2h")])
def test_round_ties_away_from_zero(text: str, expected: str) -> None:
    assert Duration(text).round(largest="hour", smallest="hour") == Duration(expected)


@pytest.mark.parametrize(
    ("mode", "positive", "negative"),
    [
        ("ceil", "2h", "-1h"),
        ("floor", "1h", "-2h"),
        ("expand", "2h", "-2h"),
        ("trunc", "1h", "-1h"),
        ("half_ceil", "2h", "-1h"),
        ("half_floor", "1h", "-2h"),
        ("half_expand", "2h", "-2h"),
        ("half_trunc", "1h", "-1h"),
        ("half_even", "2h", "-2h"),
    ],
)
def test_round_modes_handle_positive_and_negative_ties(
    mode: str,
    positive: str,
    negative: str,
) -> None:
    assert Duration("90m").round(
        largest="hour",
        smallest="hour",
        mode=mode,  # pyrefly: ignore[bad-argument-type]
    ) == Duration(positive)
    assert Duration("-90m").round(
        largest="hour",
        smallest="hour",
        mode=mode,  # pyrefly: ignore[bad-argument-type]
    ) == Duration(negative)


def test_round_half_even_selects_even_multiples() -> None:
    assert Duration("2h 30m").round(
        largest="hour", smallest="hour", mode="half_even"
    ) == Duration("2h")
    assert Duration("12m 30s").round(
        largest="minute", smallest="minute", increment=5, mode="half_even"
    ) == Duration("10m")
    assert Duration("7m 30s").round(
        largest="minute", smallest="minute", increment=5, mode="half_even"
    ) == Duration("10m")


def test_round_increments_apply_the_selected_mode() -> None:
    assert Duration("1h 10m").round(
        largest="hour", smallest="minute", increment=15, mode="ceil"
    ) == Duration("1h 15m")
    assert Duration("-1h 10m").round(
        largest="hour", smallest="minute", increment=15, mode="floor"
    ) == Duration("-1h 15m")
    assert Duration("4h 2m 30s").round(
        largest="hour", smallest="minute", increment=5
    ) == Duration("4h 5m")


def test_round_calendar_increments_use_the_reference() -> None:
    assert Duration("10mo 15d").round(
        largest="month",
        smallest="month",
        increment=3,
        mode="trunc",
        relative_to=date(2024, 1, 1),
    ) == Duration("9mo")
    zero = Duration("0s").round(
        largest="year",
        smallest="year",
        increment=1_000_000_000,
        relative_to=date(2024, 1, 1),
    )
    assert zero.is_zero()


@pytest.mark.parametrize(
    ("smallest", "increment"),
    [
        ("nanosecond", 0),
        ("nanosecond", -1),
        ("nanosecond", 7),
        ("nanosecond", 1000),
        ("minute", 7),
        ("minute", 60),
        ("hour", 24),
        ("day", 1_000_000_001),
        ("year", 1_000_000_001),
    ],
)
def test_round_rejects_invalid_increments(
    smallest: Literal["nanosecond", "minute", "hour", "day", "year"], increment: int
) -> None:
    with pytest.raises(DurationRoundError, match="round"):
        _ = Duration("0s").round(
            largest=smallest,
            smallest=smallest,
            increment=increment,
            relative_to=date(2024, 1, 1),
        )


def test_round_rejects_an_unknown_mode() -> None:
    with pytest.raises(DurationRoundError) as error:
        _ = Duration("1h").round(largest="hour", mode="unknown")  # pyrefly: ignore[bad-argument-type]
    assert isinstance(error.value, ChronosapienError)
    assert str(error.value) == 'unknown rounding mode: "unknown"'


@pytest.mark.parametrize(
    "relative_to", [None, date(2024, 1, 1), datetime(2024, 1, 1, tzinfo=UTC)]
)
def test_round_rejects_an_invalid_increment_for_nonzero_spans(
    relative_to: date | None,
) -> None:
    with pytest.raises(DurationRoundError, match="round"):
        _ = Duration("5m").round(
            largest="minute", smallest="minute", increment=7, relative_to=relative_to
        )


def test_round_rejects_reversed_units() -> None:
    with pytest.raises(InvalidUnitError) as error:
        _ = Duration("1h").round(largest="minute", smallest="hour")
    assert str(error.value) == "largest must be at least as large as smallest."


@pytest.mark.parametrize("unit", ["month", "year"])
def test_round_requires_a_reference_for_months_and_years(
    unit: Literal["month", "year"],
) -> None:
    expected = "relative_to is required for years or months. Pass a date or datetime."
    with pytest.raises(CalendarUnitError) as error:
        _ = Duration(f"1 {unit}").round(largest="hour")
    assert str(error.value) == expected

    with pytest.raises(CalendarUnitError) as error:
        _ = Duration("24h").round(largest=unit)
    assert str(error.value) == expected


@pytest.mark.parametrize(
    "relative_to", [None, date(2024, 1, 1), datetime(2024, 1, 1, tzinfo=UTC)]
)
@pytest.mark.parametrize("increment", [1, 2])
def test_round_out_of_range_raises_duration_round_error(
    relative_to: date | None, increment: int
) -> None:
    with pytest.raises(DurationRoundError, match="nanosecond"):
        _ = Duration("200000d").round(
            largest="nanosecond", increment=increment, relative_to=relative_to
        )


def test_round_out_of_range_reference_calculation_raises_duration_round_error() -> None:
    with pytest.raises(DurationRoundError):
        _ = Duration("1mo").round(largest="month", relative_to=date.max)


def test_span_arithmetic_uses_fixed_days_and_weeks_without_a_reference() -> None:
    week = Duration("1w")

    assert week.plus(Duration("6d 24h")) == Duration("2w")
    assert week.minus(Duration("169h")) == Duration("-1h")


@pytest.mark.parametrize(("left", "right"), [("1mo", "1h"), ("1h", "1y")])
def test_span_arithmetic_requires_a_reference_for_months_and_years(
    left: str, right: str
) -> None:
    first, second = Duration(left), Duration(right)

    with pytest.raises(CalendarUnitError, match="relative_to is required"):
        _ = first.plus(second)
    with pytest.raises(CalendarUnitError, match="relative_to is required"):
        _ = first.minus(second)


def test_span_arithmetic_accepts_a_date_reference() -> None:
    month, days = Duration("1mo"), Duration("28d")

    assert month.minus(days, relative_to=date(2025, 2, 1)).is_zero()
    assert month.minus(days, relative_to=date(2025, 1, 1)) == Duration("3d")


def test_span_arithmetic_reports_an_out_of_range_result() -> None:
    with pytest.raises(ValueError, match="hour"):
        _ = Duration("175307616h").plus(Duration("1h"))


@pytest.mark.parametrize(
    "zone",
    [None, timezone(timedelta(hours=5, minutes=30))],
    ids=["naive", "fixed-offset"],
)
def test_month_arithmetic_clamps_to_end_of_february(zone: tzinfo | None) -> None:
    month = Duration("1mo")
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


@pytest.mark.parametrize(
    "delta",
    [timedelta(), timedelta(days=2, microseconds=42), timedelta(microseconds=-1501)],
)
def test_from_timedelta_round_trips(delta: timedelta) -> None:
    assert Duration.from_timedelta(delta).to_timedelta() == delta


@pytest.mark.parametrize("delta", [timedelta.min, timedelta.max])
def test_from_timedelta_rejects_out_of_range_values(delta: timedelta) -> None:
    with pytest.raises(OverflowError, match="seconds"):
        _ = Duration.from_timedelta(delta)


def test_between_dates_supports_calendar_units() -> None:
    start = date(2025, 1, 30)
    end = date(2025, 3, 2)

    assert Duration.between(start, end) == Duration("31d")
    assert Duration.between(start, end, largest="month") == Duration("1mo 2d")
    assert Duration.between(end, start, largest="month") == Duration("-1mo 3d")
    assert Duration.between(end, start) == Duration("-31d")
    assert Duration.between(start, start).is_zero()


def test_between_naive_datetimes_preserves_subseconds() -> None:
    start = datetime(2025, 1, 30, 9)
    end = datetime(2025, 1, 31, 10, 30, 0, 123456)

    assert Duration.between(start, end) == Duration("1d 1h 30m 123ms 456us")
    assert Duration.between(start, end, largest="hour") == Duration(
        "25h 30m 123ms 456us"
    )
    assert Duration.between(end, start, largest="hour") == Duration(
        "-25h 30m 123ms 456us"
    )


def test_between_aware_datetimes_accounts_for_dst() -> None:
    try:
        zone = ZoneInfo("America/New_York")
    except ZoneInfoNotFoundError:
        pytest.skip("America/New_York time zone data is unavailable")

    start = datetime(2024, 3, 10, tzinfo=zone)
    end = datetime(2024, 3, 11, tzinfo=zone)

    assert Duration.between(start, end) == Duration("23h")
    assert Duration.between(start, end, largest="day") == Duration("1d")

    first = datetime(2024, 11, 3, 1, 30, tzinfo=zone, fold=0)
    second = datetime(2024, 11, 3, 1, 30, tzinfo=zone, fold=1)
    assert Duration.between(first, second) == Duration("1h")


def test_between_aware_datetimes_in_different_time_zones() -> None:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    end = datetime(2024, 1, 1, 5, 30, tzinfo=timezone(timedelta(hours=5, minutes=30)))

    assert Duration.between(start, end).is_zero()
    assert Duration.between(start, end, largest="day").is_zero()
    end += timedelta(hours=1)
    assert Duration.between(start, end) == Duration("1h")
    with pytest.raises(ValueError, match="(?i)time.?zone"):
        _ = Duration.between(start, end, largest="day")


def test_between_rejects_incompatible_endpoints_and_units() -> None:
    day = date(2025, 1, 1)
    naive = datetime(2025, 1, 1)
    aware = datetime(2025, 1, 1, tzinfo=UTC)

    with pytest.raises(TypeError, match="dates or both be datetimes"):
        _ = Duration.between(day, naive)
    with pytest.raises(TypeError, match="naive or both be aware"):
        _ = Duration.between(naive, aware)
    with pytest.raises(InvalidUnitError):
        _ = Duration.between(day, day, largest="fortnight")  # pyrefly: ignore[bad-argument-type]
    with pytest.raises(ValueError):
        _ = Duration.between(day, day, largest="hour")
    with pytest.raises(ValueError, match="nanosecond"):
        _ = Duration.between(
            datetime(1800, 1, 1), datetime(2200, 1, 1), largest="nanosecond"
        )


def test_spring_dst_transition_makes_calendar_day_23_hours() -> None:
    try:
        zone = ZoneInfo("America/New_York")
    except ZoneInfoNotFoundError:
        pytest.skip("America/New_York time zone data is unavailable")

    midnight_before = datetime(2024, 3, 10, tzinfo=zone)
    midnight_after = datetime(2024, 3, 11, tzinfo=zone)
    calendar_day = Duration("1d")
    fixed_day = Duration.from_timedelta(timedelta(days=1))

    assert calendar_day.to_timedelta(relative_to=midnight_before) == timedelta(hours=23)
    assert fixed_day.add_to(midnight_before) == datetime(2024, 3, 11, 1, tzinfo=zone)
    assert calendar_day.equivalent_to(Duration("23h"), relative_to=midnight_before)
    assert (
        calendar_day.compare(Duration("24h"), relative_to=midnight_before)
        is Ordering.LESS
    )
    assert calendar_day.minus(Duration("23h"), relative_to=midnight_before).is_zero()
    extended_day = calendar_day.plus(Duration("1h"), relative_to=midnight_before)
    assert extended_day.add_to(midnight_before) == datetime(2024, 3, 11, 1, tzinfo=zone)
    assert calendar_day.total("hour", relative_to=midnight_before) == 23.0
    assert Duration("23h").total("day", relative_to=midnight_before) == 1.0
    assert Duration("23h").round(largest="day") == Duration("23h")
    assert (
        Duration("23h").round(largest="day", relative_to=midnight_before)
        == calendar_day
    )
    assert Duration("23h 5m").round(
        largest="day",
        smallest="minute",
        increment=15,
        mode="ceil",
        relative_to=midnight_before,
    ) == Duration("1d 15m")
    assert to_timedelta("1d", relative_to=midnight_before) == timedelta(hours=23)
    assert to_timedelta("1d", relative_to=None) == timedelta(hours=24)

    added = calendar_day.add_to(midnight_before)
    assert added == midnight_after
    assert added.tzinfo == zone

    subtracted = calendar_day.subtract_from(midnight_after)
    assert subtracted == midnight_before
    assert subtracted.tzinfo == zone


def test_unsupported_timezone_raises_type_error() -> None:
    start = datetime(2024, 3, 10, tzinfo=tzinfo())

    with pytest.raises(TypeError, match="naive datetime"):
        _ = Duration("1d").to_timedelta(relative_to=start)
    with pytest.raises(TypeError, match="naive datetime"):
        _ = Duration("1d").round(largest="day", relative_to=start)


def test_span_sign_predicates() -> None:
    assert Duration("2h").is_positive()
    assert Duration("-2h").is_negative()

    zero = Duration("0s")
    assert zero.is_zero()
    assert not zero.is_positive()
    assert not zero.is_negative()


def test_abs_and_negate() -> None:
    positive = Duration("2h")
    negative = Duration("-2h")

    assert negative.abs() == positive
    assert positive.negate() == negative


def test_scaling_keeps_original_units() -> None:
    span = Duration("50m")

    assert span.scale(-2) == Duration("-100m")
    assert span.scale(0) == Duration("0s")


@pytest.mark.parametrize(
    "factor",
    [
        pytest.param(100_000, id="scaled-years-out-of-range"),
        pytest.param(2**63, id="factor-out-of-range"),
    ],
)
def test_scale_overflow(factor: int) -> None:
    with pytest.raises(OverflowError):
        _ = Duration("1y").scale(factor)
