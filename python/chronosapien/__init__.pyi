"""Parse fixed durations and calendar spans using Jiff."""

from datetime import date, datetime, timedelta
from enum import IntEnum
from typing import Final, Literal, TypeAlias, final

__all__: Final = (
    "CalendarUnitError",
    "ChronosapienError",
    "Duration",
    "DurationFormatError",
    "DurationFormatter",
    "DurationRoundError",
    "InvalidUnitError",
    "Ordering",
    "SpanParseError",
    "to_timedelta",
)

def __dir__() -> list[str]: ...

SpanUnit: TypeAlias = Literal[
    "year",
    "month",
    "week",
    "day",
    "hour",
    "minute",
    "second",
    "millisecond",
    "microsecond",
    "nanosecond",
]

class ChronosapienError(Exception):
    """Base class for Chronosapien's custom exceptions."""

class CalendarUnitError(ChronosapienError):
    """A year or month requires a reference date and none was supplied."""

class DurationFormatError(ChronosapienError):
    """An unknown formatting option value or an unsupported precision or padding."""

class DurationRoundError(ChronosapienError):
    """An unknown rounding mode or a failure to round a duration."""

class InvalidUnitError(ChronosapienError):
    """An unknown unit name or invalid ordering of rounding units."""

class SpanParseError(ChronosapienError):
    """Invalid span text or a component outside its supported range."""

class Ordering(IntEnum):
    """
    Named results for comparing durations by elapsed time.
    """

    LESS = -1
    EQUAL = 0
    GREATER = 1

def to_timedelta(text: str, /, *, relative_to: date | None = None) -> timedelta:
    """
    Parse an ISO 8601 or human-readable duration into a `timedelta`.
    For more input examples, see [Jiff's friendly format](https://docs.rs/jiff/latest/jiff/fmt/friendly/index.html).

    Without a reference, a day is 24 hours and a week is seven days.
    Supply `relative_to` when the span has nonzero months or years. The
    reference can be a `date` or a `datetime`. A `datetime` can be naive or
    use `datetime.timezone` or a named `zoneinfo.ZoneInfo`. Named zones
    account for offset transitions.

    Fractional seconds in fixed offsets and fractional microseconds in the
    result are truncated toward zero.

    Raises
    ------
    TypeError
        If `text` is not a string or the reference has an unsupported type or `tzinfo`.
    SpanParseError
        If the duration syntax is invalid or a component is out of range.
    CalendarUnitError
        If the span has nonzero years or months and no reference was supplied.
    ValueError
        If the `ZoneInfo` key is missing or unrecognized, or the reference or
        result is out of range.

    Examples
    --------
    ```python
    from datetime import date, timedelta

    from chronosapien import to_timedelta

    # One day is 24 hours, so adding two hours gives 26.
    assert to_timedelta("1 day 2 hours") == timedelta(hours=26)
    # P1DT2H is the ISO 8601 spelling of one day and two hours.
    assert to_timedelta("P1DT2H") == to_timedelta("1 day 2 hours")
    # One month starting on February 1 lasts 28 days in 2026.
    assert to_timedelta("1mo", relative_to=date(2026, 2, 1)) == timedelta(days=28)
    ```
    """

@final
class Duration:
    def __new__(cls, text: str, /) -> Duration:
        """
        An immutable span of time represented via a mixture of calendar and clock
        units, parsed from an ISO 8601 or human-readable string.
        For more input examples, see [Jiff's friendly format](https://docs.rs/jiff/latest/jiff/fmt/friendly/index.html).

        It represents a duration of time in units of years, months, weeks, days,
        hours, minutes, seconds, milliseconds, microseconds and nanoseconds.

        Raises
        ------
        TypeError
            If the constructor call supplies anything other than one positional `str`.
        SpanParseError
            If the span syntax is invalid or a component is out of range.

        Examples
        --------
        ```python
        from chronosapien import Duration

        span = Duration("1mo 2d")
        # Omitted units, such as hours here, read as zero.
        assert (span.months, span.days, span.hours) == (1, 2, 0)

        span = Duration("90m")
        # The span keeps all 90 minutes in the minutes field.
        assert (span.minutes, span.hours) == (90, 0)
        ```
        """

    @staticmethod
    def from_timedelta(delta: timedelta, /) -> Duration:
        """
        Build a duration from the fixed elapsed time in a `timedelta`.

        The result stores whole seconds and subsecond units. Each day in the
        `timedelta` becomes 86,400 seconds, including when the resulting duration
        is applied across a time zone offset change.

        Raises
        ------
        TypeError
            If `delta` is not a `timedelta`.
        OverflowError
            If `delta` is outside the supported range for a `Duration`.

        Examples
        --------
        ```python
        from datetime import timedelta

        from chronosapien import Duration

        day = timedelta(days=1)
        duration = Duration.from_timedelta(day)
        assert duration == Duration("86400s")
        assert duration.to_timedelta() == day
        ```
        """

    @staticmethod
    def between(
        start: date, end: date, /, *, largest: SpanUnit | None = None
    ) -> Duration:
        """
        Return the span from `start` to `end`.

        Both endpoints must be dates or both must be datetimes. Datetimes
        must both be naive or both be aware. Aware datetimes can use
        `datetime.timezone` or a named `zoneinfo.ZoneInfo`. Named zones account
        for offset transitions. Fractional seconds in fixed offsets are
        truncated toward zero.

        `largest` sets the largest unit in the result. It accepts singular
        unit names from `"nanosecond"` through `"year"`. For dates, the
        largest unit must be `"day"`, `"week"`, `"month"`, or `"year"`.
        When `largest` is omitted, it defaults to `"day"` for dates and
        naive datetimes, and `"hour"` for aware datetimes. For a nonzero
        difference with `largest` set to `"day"` or greater, aware datetimes
        must have matching time zones.

        The result is negative when `end` precedes `start`. Calendar spans
        are calculated relative to `start`, so reversing the endpoints can
        yield different components around month ends or offset transitions.

        Raises
        ------
        TypeError
            If the endpoints have incompatible types or awareness, or use an
            unsupported `tzinfo`.
        InvalidUnitError
            If `largest` is an unknown unit name.
        ValueError
            If `largest` is a time unit for dates, the time zones are incompatible
            for calendar units, a `ZoneInfo` key is missing or unrecognized, or
            the result is outside the supported range.

        Examples
        --------
        ```python
        from datetime import date, datetime

        from chronosapien import Duration

        start, end = date(2025, 1, 30), date(2025, 3, 2)
        assert Duration.between(start, end) == Duration("31d")
        assert Duration.between(start, end, largest="month") == Duration("1mo 2d")
        assert Duration.between(end, start, largest="month") == Duration("-1mo 3d")

        start_time = datetime(2025, 1, 30, 9)
        end_time = datetime(2025, 1, 31, 10, 30)
        assert Duration.between(start_time, end_time, largest="hour") == Duration("25h 30m")
        ```
        """

    def to_timedelta(self, *, relative_to: date | None = None) -> timedelta:
        """
        Return elapsed time as a `timedelta`.

        Without a reference, a day is 24 hours and a week is seven days.
        Supply `relative_to` when the span has nonzero months or years.

        `relative_to` accepts a `date` or a `datetime`. A `datetime` can be
        naive or use `datetime.timezone` or a named `zoneinfo.ZoneInfo`.
        Named zones account for offset transitions.

        Fractional seconds in fixed offsets and fractional microseconds in the
        result are truncated toward zero.

        Raises
        ------
        TypeError
            If a supplied reference has an unsupported type or `tzinfo`.
        CalendarUnitError
            If the span has nonzero months or years and no reference was supplied.
        ValueError
            If the `ZoneInfo` key is missing or unrecognized, or the reference or
            result is out of range.

        Examples
        --------
        ```python
        from datetime import date, timedelta

        from chronosapien import Duration

        assert Duration("1d").to_timedelta() == timedelta(hours=24)

        month = Duration("1mo")
        # January 1 to February 1 is 31 days.
        assert month.to_timedelta(relative_to=date(2026, 1, 1)).days == 31
        # February 1 to March 1 is 28 days in 2026.
        assert month.to_timedelta(relative_to=date(2026, 2, 1)).days == 28
        ```
        """

    def total(self, unit: SpanUnit, /, *, relative_to: date | None = None) -> float:
        """
        Return the span as a possibly fractional number of the given unit.

        `unit` is a singular unit name from `"nanosecond"` through `"year"`.
        Without a reference, a day is 24 hours and a week is seven days.
        Supply `relative_to` when the span has nonzero months or years, or
        when `unit` is `"month"` or `"year"`. The reference can be a `date` or
        a `datetime`. A `datetime` can be naive or use `datetime.timezone` or
        a named `zoneinfo.ZoneInfo`. Named zones account for offset transitions.
        Fractional seconds in fixed offsets are truncated toward zero.

        Raises
        ------
        TypeError
            If `unit` is not a string or the reference has an unsupported type or `tzinfo`.
        InvalidUnitError
            If `unit` is an unknown unit name.
        CalendarUnitError
            If the span has nonzero months or years or the target is one of those
            units, and no reference was supplied.
        ValueError
            If the `ZoneInfo` key is missing or unrecognized, or the reference or
            result is out of range.

        Examples
        --------
        ```python
        from datetime import date

        from chronosapien import Duration

        assert Duration("90m").total("hour") == 1.5
        assert Duration("36h").total("day") == 1.5
        assert Duration("1mo").total("day", relative_to=date(2026, 2, 1)) == 28.0
        ```
        """

    def round(
        self,
        *,
        largest: SpanUnit,
        smallest: SpanUnit = "nanosecond",
        increment: int = 1,
        mode: Literal[
            "ceil",
            "floor",
            "expand",
            "trunc",
            "half_ceil",
            "half_floor",
            "half_expand",
            "half_trunc",
            "half_even",
        ] = "half_expand",
        relative_to: date | None = None,
    ) -> Duration:
        """
        Return a new span rounded and balanced between `largest` and `smallest`.

        Both bounds take singular unit names from `"nanosecond"` through `"year"`.
        `largest` caps the units in the result. The default `smallest` preserves
        nanosecond precision.

        `increment` sets the rounding increment in units of `smallest`. It
        must be between 1 and 1,000,000,000. For units smaller than a day, it
        must be less than the number of those units in the next larger unit
        and divide that number evenly. For example, 15 and 30 are valid minute
        increments, while 7 and 60 are not. The default increment is 1.

        `mode` controls the direction of rounding. `"ceil"` rounds toward
        positive infinity, `"floor"` toward negative infinity, `"expand"` away
        from zero, and `"trunc"` toward zero. The remaining modes round to the
        nearest increment and differ in how they handle ties.

        - `"half_ceil"` rounds ties toward positive infinity.
        - `"half_floor"` rounds ties toward negative infinity.
        - `"half_expand"` rounds ties away from zero.
        - `"half_trunc"` rounds ties toward zero.
        - `"half_even"` rounds ties to an even multiple of the increment.

        The default mode is `"half_expand"`. For example, with
        `largest="hour"`, `smallest="minute"`, `increment=15`, and
        `mode="ceil"`, `1h 10m` rounds to `1h 15m`.

        Without a reference, a day is 24 hours and a week is seven days.
        Supply `relative_to` when the span has nonzero months or years, or when
        either bound is `"month"` or `"year"`. The reference can be a `date`, a
        naive `datetime`, or a `datetime` with `datetime.timezone` or a named
        `zoneinfo.ZoneInfo`. Named zones account for offset transitions.
        Fractional seconds in fixed offsets are truncated toward zero.

        Raises
        ------
        TypeError
            If either bound or `mode` is not a string, `increment` is not an
            integer, or the reference has an unsupported type or `tzinfo`.
        InvalidUnitError
            If a unit name is unknown or `largest` is smaller than `smallest`.
        DurationRoundError
            If `mode` is unknown, `increment` is invalid for the smallest unit,
            or the rounding calculation exceeds the supported range.
        CalendarUnitError
            If months or years are involved and no reference was supplied.
        ValueError
            If the `ZoneInfo` key is missing or unrecognized, or the reference
            is out of range.

        Examples
        --------
        ```python
        from chronosapien import Duration

        span = Duration("119m 31s")
        assert span.round(largest="hour") == Duration("1h 59m 31s")
        assert span.round(largest="hour", smallest="minute") == Duration("2h")
        assert Duration("1h 10m").round(
            largest="hour", smallest="minute", increment=15, mode="ceil"
        ) == Duration("1h 15m")
        assert Duration("2h 30m").round(
            largest="hour", smallest="hour", mode="half_even"
        ) == Duration("2h")
        ```
        """

    def compare(
        self, other: Duration, /, *, relative_to: date | None = None
    ) -> Ordering:
        """
        Compare this span's elapsed time with `other` at nanosecond precision.

        Return `Ordering.LESS` (-1), `Ordering.EQUAL` (0), or
        `Ordering.GREATER` (1) according to the signed elapsed times.

        Supply `relative_to` as the starting point for both spans when either has
        nonzero months or years. Without a reference, a day is 24 hours and a week
        is seven days. The reference can be a `date` or a `datetime`. A `datetime`
        may be naive, have a fixed offset from `datetime.timezone`, or use a named
        `zoneinfo.ZoneInfo`. Named zones account for offset transitions.
        Fixed offsets are truncated toward zero to whole seconds.

        Raises
        ------
        TypeError
            If `other` is not a `Duration` or the reference has an unsupported
            type or `tzinfo`.
        CalendarUnitError
            If either span has nonzero months or years and no reference was supplied.
        ValueError
            If the `ZoneInfo` key is missing or unrecognized, or the reference or
            either result is out of range.

        Examples
        --------
        ```python
        from datetime import date

        from chronosapien import Duration, Ordering

        assert Duration("1h").compare(Duration("60m")) is Ordering.EQUAL
        assert Duration("30m").compare(Duration("1h")) == -1 == Ordering.LESS

        month, days = Duration("1mo"), Duration("30d")
        assert month.compare(days, relative_to=date(2026, 1, 1)) is Ordering.GREATER
        assert month.compare(days, relative_to=date(2026, 2, 1)) is Ordering.LESS
        ```
        """

    def equivalent_to(
        self, other: Duration, /, *, relative_to: date | None = None
    ) -> bool:
        """
        Return whether both spans have the same elapsed time at nanosecond precision.

        Supply `relative_to` as the starting point for both spans when either has
        nonzero months or years. Without a reference, a day is 24 hours and a week
        is seven days. A `datetime` may be naive,
        have a fixed offset from `datetime.timezone`, or use a named
        `zoneinfo.ZoneInfo`. Named zones account for offset transitions.
        Fixed offsets are truncated toward zero to whole seconds.

        Raises
        ------
        TypeError
            If `other` is not a `Duration` or the reference has an unsupported
            type or `tzinfo`.
        CalendarUnitError
            If either span has nonzero months or years and no reference was supplied.
        ValueError
            If the `ZoneInfo` key is missing or unrecognized, or the reference or
            either result is out of range.

        Examples
        --------
        ```python
        from datetime import date

        from chronosapien import Duration

        assert Duration("1h").equivalent_to(Duration("60m"))
        assert Duration("1w").equivalent_to(Duration("168h"))

        month, days = Duration("1mo"), Duration("28d")
        # From February 1, both spans reach March 1.
        assert month.equivalent_to(days, relative_to=date(2026, 2, 1))
        # From January 1, reaching February 1 takes 31 days.
        assert not month.equivalent_to(days, relative_to=date(2026, 1, 1))
        ```
        """

    def plus(self, other: Duration, /, *, relative_to: date | None = None) -> Duration:
        """
        Add two spans and return a new, balanced `Duration`.

        With `relative_to`, apply this span first and then `other`. The result
        describes the difference between the reference and the final time.
        The order of the spans can affect the result around month ends or
        offset transitions.

        Supply `relative_to` when either span has nonzero months or years.
        Without a reference, a day is 24 hours and a week is seven days.
        The reference can be a `date` or a `datetime`. A `datetime` can be
        naive or use `datetime.timezone` or a named `zoneinfo.ZoneInfo`.
        Named zones account for offset transitions. Fractional seconds in
        fixed offsets are truncated toward zero.

        Raises
        ------
        TypeError
            If `other` is not a `Duration` or the reference has an unsupported
            type or `tzinfo`.
        CalendarUnitError
            If either span has nonzero months or years and no reference was supplied.
        ValueError
            If the `ZoneInfo` key is missing or unrecognized, or the arithmetic
            exceeds the supported range.

        Examples
        --------
        ```python
        from datetime import datetime

        from chronosapien import Duration

        assert Duration("1h").plus(Duration("90m")) == Duration("2h 30m")

        start = datetime(2025, 1, 30)
        month, days = Duration("1mo"), Duration("2d")
        assert month.plus(days, relative_to=start).add_to(start) == datetime(2025, 3, 2)
        assert days.plus(month, relative_to=start).add_to(start) == datetime(2025, 3, 1)
        ```
        """

    def minus(self, other: Duration, /, *, relative_to: date | None = None) -> Duration:
        """
        Subtract `other` from this span and return a new, balanced `Duration`.

        With `relative_to`, apply this span first and then the negation of
        `other`. The result describes the difference between the reference
        and the final time.

        Supply `relative_to` when either span has nonzero months or years.
        Without a reference, a day is 24 hours and a week is seven days.
        The reference can be a `date` or a `datetime`. A `datetime` can be
        naive or use `datetime.timezone` or a named `zoneinfo.ZoneInfo`.
        Named zones account for offset transitions. Fractional seconds in
        fixed offsets are truncated toward zero.

        Raises
        ------
        TypeError
            If `other` is not a `Duration` or the reference has an unsupported
            type or `tzinfo`.
        CalendarUnitError
            If either span has nonzero months or years and no reference was supplied.
        ValueError
            If the `ZoneInfo` key is missing or unrecognized, or the arithmetic
            exceeds the supported range.

        Examples
        --------
        ```python
        from datetime import date

        from chronosapien import Duration

        assert Duration("1h").minus(Duration("90m")) == Duration("-30m")

        month, days = Duration("1mo"), Duration("28d")
        assert month.minus(days, relative_to=date(2025, 2, 1)).is_zero()
        ```
        """

    def add_to(self, start: datetime) -> datetime:
        """
        Add the span to a `datetime` and return the resulting `datetime`.

        `start` accepts a naive `datetime` or one with `datetime.timezone` or
        a named `zoneinfo.ZoneInfo`. Month arithmetic clamps the day to the end
        of the target month when needed.

        Fixed offsets are truncated toward zero to whole seconds.
        The resulting fixed-offset timezone uses Python's default name.

        Raises
        ------
        TypeError
            If `start` is not a `datetime` or has unsupported `tzinfo`.
        ValueError
            If the `ZoneInfo` key is missing or unrecognized, or the starting
            or resulting `datetime` is outside the supported range.

        Examples
        --------
        ```python
        from datetime import datetime

        from chronosapien import Duration

        start = datetime(2026, 1, 31, 9)
        # February 2026 has only 28 days, so the 31st becomes the 28th.
        assert Duration("1mo").add_to(start) == datetime(2026, 2, 28, 9)
        ```
        """

    def subtract_from(self, start: datetime) -> datetime:
        """
        Subtract the span from a `datetime` and return the resulting `datetime`.

        `start` accepts a naive `datetime` or one with `datetime.timezone` or
        a named `zoneinfo.ZoneInfo`. If the day falls beyond the end of the target
        month, it becomes the last day of that month.

        Fixed offsets are truncated toward zero to whole seconds.
        The resulting fixed-offset timezone uses Python's default name.

        Raises
        ------
        TypeError
            If `start` is not a `datetime` or has unsupported `tzinfo`.
        ValueError
            If the `ZoneInfo` key is missing or unrecognized, or the starting
            or resulting `datetime` is outside the supported range.

        Examples
        --------
        ```python
        from datetime import datetime

        from chronosapien import Duration

        start = datetime(2026, 3, 31, 9)
        # Subtracting a month targets February, which ends on the 28th in 2026.
        assert Duration("1mo").subtract_from(start) == datetime(2026, 2, 28, 9)
        ```
        """

    def is_zero(self) -> bool:
        """Return whether every unit of the span is zero.

        Examples
        --------
        ```python
        from chronosapien import Duration

        assert Duration("0s").is_zero()
        ```
        """

    def __bool__(self) -> bool:
        """Return whether any stored unit is nonzero.

        Examples
        --------
        ```python
        from chronosapien import Duration

        assert not bool(Duration("0s"))
        assert bool(Duration("1ns"))
        assert bool(Duration("-1mo"))
        ```
        """

    def is_positive(self) -> bool:
        """Return whether the span is strictly positive.

        Examples
        --------
        ```python
        from chronosapien import Duration

        assert Duration("1mo").is_positive()
        ```
        """

    def is_negative(self) -> bool:
        """Return whether the span is strictly negative.

        Examples
        --------
        ```python
        from chronosapien import Duration

        assert Duration("-2h").is_negative()
        ```
        """

    def abs(self) -> Duration:
        """Return the absolute value of the span.

        Examples
        --------
        ```python
        from chronosapien import Duration

        assert Duration("-2h").abs() == Duration("2h")
        ```
        """

    def negate(self) -> Duration:
        """Return a span with the opposite sign.

        Examples
        --------
        ```python
        from chronosapien import Duration

        assert Duration("2h").negate() == Duration("-2h")
        ```
        """

    def scale(self, n: int, /) -> Duration:
        """Return a new span with each stored unit multiplied by `n`.

        Raises
        ------
        TypeError
            If `n` is passed by keyword or cannot be interpreted as an integer.
        OverflowError
            If `n` is outside the signed 64-bit integer range or a scaled
            component is out of range.

        Examples
        --------
        ```python
        from chronosapien import Duration

        scaled = Duration("50m").scale(2)
        # Doubling 50 minutes stores 100 in the minutes field.
        assert (scaled.hours, scaled.minutes) == (0, 100)
        ```
        """

    def __str__(self) -> str:
        """Format the span as an ISO 8601 duration.

        Examples
        --------
        ```python
        from chronosapien import Duration

        assert str(Duration("1mo 2d")) == "P1M2D"
        ```
        """

    def __repr__(self) -> str:
        """Return a constructor expression using Jiff's friendly format.

        Examples
        --------
        ```python
        from chronosapien import Duration

        assert repr(Duration("P1M2D")) == "Duration('1mo 2d')"
        ```
        """

    def __copy__(self) -> Duration:
        """Return this immutable duration from `copy.copy()`.

        Examples
        --------
        ```python
        from copy import copy

        from chronosapien import Duration

        span = Duration("1mo 2d")
        assert copy(span) is span
        ```
        """

    def __deepcopy__(self, memo: dict[int, object], /) -> Duration:
        """Return this immutable duration from `copy.deepcopy()`.

        Examples
        --------
        ```python
        from copy import deepcopy

        from chronosapien import Duration

        span = Duration("1mo 2d")
        assert deepcopy([span])[0] is span
        ```
        """

    def to_friendly(
        self,
        *,
        designator: Literal["compact", "short", "verbose"] = "compact",
        spacing: Literal["auto", "none", "units", "designators"] = "auto",
        comma: bool | None = None,
        direction: Literal["auto", "sign", "suffix"] = "auto",
        hhmmss: bool = False,
        fractional: Literal["hour", "minute", "second", "millisecond", "microsecond"]
        | None = None,
        precision: int | None = None,
        padding: int | None = None,
    ) -> str:
        """Return a human-readable duration string.

        `designator` selects the unit labels, such as `1y` for `"compact"`,
        `1yr` for `"short"`, and `1year` for `"verbose"` with default spacing.

        `spacing` controls where spaces appear. `"none"` gives `1h30m`,
        `"units"` gives `1h 30m`, and `"designators"` gives `1 h 30 m`.
        The default, `"auto"`, uses Jiff's default spacing between units.
        Set `comma=True` to add comma separators between units. `False` and
        `None` both omit commas.

        `direction` controls how the sign is displayed. `"sign"` writes a
        leading minus on negative durations, and `"suffix"` writes `ago`
        after negative durations. The default, `"auto"`, uses a leading minus with
        `spacing="none"` or with `hhmmss=True` and no calendar units. It
        uses `ago` for other negative durations.

        `hhmmss=True` displays hours, minutes, and seconds as `HH:MM:SS`.
        Days and larger units use the selected designator. A space separates
        those units from the time even with `spacing="none"`. Minutes and
        seconds can exceed 59. Subsecond units are folded into seconds with
        nanosecond precision by default.

        `fractional` folds smaller units into a decimal, such as `1.5h` for
        `1h 30m` with `fractional="hour"`. Fractional hours and minutes can
        lose precision even with automatic precision. `hhmmss=True` uses
        fractional seconds regardless of `fractional`.

        `precision` accepts integers from 0 through 9 and sets the number of
        decimal places when fractional output is enabled. An explicit precision
        truncates excess digits. `None` uses as many places as the value needs,
        up to 9.

        `padding` accepts integers from 0 through 20 and sets the minimum width
        of the integer part of each unit, adding leading zeros as needed. With
        `padding=None`, the `HH:MM:SS` fields use a width of 2 and other fields
        have no padding.

        To reuse these options across durations, use
        [`DurationFormatter`][chronosapien.DurationFormatter].

        Raises
        ------
        TypeError
            If an argument has the wrong type.
        DurationFormatError
            If the formatter receives an unknown `designator`, `spacing`,
            `direction`, or `fractional` value, a `precision` above 9, or a
            `padding` above 20.

        Examples
        --------
        ```python
        from chronosapien import Duration

        assert Duration("P1M2D").to_friendly() == "1mo 2d"
        assert Duration("1y 2mo").to_friendly(designator="short") == "1yr 2mos"
        assert Duration("1h 30m").to_friendly(designator="verbose", spacing="designators", comma=True) == "1 hour, 30 minutes"
        assert Duration("1h 30m").to_friendly(spacing="designators") == "1 h 30 m"
        assert Duration("-1h").to_friendly(direction="sign") == "-1h"
        assert Duration("1d 120m").to_friendly(hhmmss=True) == "1d 00:120:00"
        assert Duration("1h 30m").to_friendly(fractional="hour") == "1.5h"
        assert Duration("1250ms").to_friendly(hhmmss=True, precision=3) == "00:00:01.250"
        ```
        """

    def __eq__(self, other: object, /) -> bool:
        """Compare two spans unit by unit.

        Two spans are equal when their signed values match in every unit,
        from years through nanoseconds. Omitted units count as zero.
        The comparison keeps each value in its stored unit, following
        [Jiff's fieldwise equality](https://docs.rs/jiff/latest/jiff/struct.Span.html#method.fieldwise).

        To compare elapsed time, call `span.equivalent_to(other)` and supply
        `relative_to` when either span has nonzero months or years.

        Examples
        --------
        ```python
        from chronosapien import Duration

        # Both spellings store one month and two days.
        assert Duration("P1M2D") == Duration("1mo 2d")
        # The first span stores 1 hour, and the second stores 60 minutes.
        assert Duration("1h") != Duration("60m")
        ```
        """

    def __hash__(self) -> int:
        """Return a hash based on the stored unit values.

        Examples
        --------
        ```python
        from chronosapien import Duration

        reminders = {Duration("1mo"): "renew subscription"}
        # The ISO 8601 spelling P1M produces the same dictionary key.
        assert reminders[Duration("P1M")] == "renew subscription"
        ```
        """

    @property
    def years(self) -> int:
        """The stored number of years."""

    @property
    def months(self) -> int:
        """The stored number of months."""

    @property
    def weeks(self) -> int:
        """The stored number of weeks."""

    @property
    def days(self) -> int:
        """The stored number of days."""

    @property
    def hours(self) -> int:
        """The stored number of hours."""

    @property
    def minutes(self) -> int:
        """The stored number of minutes."""

    @property
    def seconds(self) -> int:
        """The stored number of seconds."""

    @property
    def milliseconds(self) -> int:
        """The stored number of milliseconds."""

    @property
    def microseconds(self) -> int:
        """The stored number of microseconds."""

    @property
    def nanoseconds(self) -> int:
        """The stored number of nanoseconds."""

@final
class DurationFormatter:
    """An immutable formatter that stores settings for human-readable durations.

    Examples
    --------
    ```python
    from chronosapien import Duration, DurationFormatter

    formatter = DurationFormatter(hhmmss=True, precision=3)
    duration = Duration("1250ms")

    assert formatter.format(duration) == "00:00:01.250"
    assert formatter.format(Duration("1h 30m")) == "01:30:00.000"
    ```
    """

    def __new__(
        cls,
        *,
        designator: Literal["compact", "short", "verbose"] = "compact",
        spacing: Literal["auto", "none", "units", "designators"] = "auto",
        comma: bool | None = None,
        direction: Literal["auto", "sign", "suffix"] = "auto",
        hhmmss: bool = False,
        fractional: Literal["hour", "minute", "second", "millisecond", "microsecond"]
        | None = None,
        precision: int | None = None,
        padding: int | None = None,
    ) -> DurationFormatter:
        """Validate and store the options described in
        [`Duration.to_friendly()`][chronosapien.Duration.to_friendly].

        Raises
        ------
        TypeError
            If an argument has the wrong type.
        DurationFormatError
            If the formatter receives an unknown `designator`, `spacing`,
            `direction`, or `fractional` value, a `precision` above 9, or a
            `padding` above 20.
        """

    def format(self, duration: Duration, /) -> str:
        """Format a duration using the stored settings."""

    def __copy__(self) -> DurationFormatter:
        """Return this immutable formatter from `copy.copy()`.

        Examples
        --------
        ```python
        from copy import copy

        from chronosapien import DurationFormatter

        formatter = DurationFormatter(hhmmss=True)
        assert copy(formatter) is formatter
        ```
        """

    def __deepcopy__(self, memo: dict[int, object], /) -> DurationFormatter:
        """Return this immutable formatter from `copy.deepcopy()`.

        Examples
        --------
        ```python
        from copy import deepcopy

        from chronosapien import DurationFormatter

        formatter = DurationFormatter(hhmmss=True)
        assert deepcopy([formatter])[0] is formatter
        ```
        """
