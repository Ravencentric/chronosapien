"""Parse fixed durations and calendar spans using Jiff."""

from datetime import date, datetime, timedelta
from typing import Final, Literal, final

__all__: Final = (
    "CalendarSpan",
    "CalendarUnitError",
    "ChronosapienError",
    "InvalidUnitError",
    "SpanParseError",
    "duration",
)

class ChronosapienError(Exception):
    """Base class for Chronosapien's custom exceptions."""

class CalendarUnitError(ChronosapienError):
    """A year or month requires a reference date and none was supplied."""

class InvalidUnitError(ChronosapienError):
    """An unknown unit was passed to `CalendarSpan.total()`."""

class SpanParseError(ChronosapienError):
    """Invalid span text or a component outside its supported range."""

def duration(text: str, /, *, relative_to: date | None = None) -> timedelta:
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

    from chronosapien import duration

    # One day is 24 hours, so adding two hours gives 26.
    assert duration("1 day 2 hours") == timedelta(hours=26)
    # P1DT2H is the ISO 8601 spelling of one day and two hours.
    assert duration("P1DT2H") == duration("1 day 2 hours")
    # One month starting on February 1 lasts 28 days in 2026.
    assert duration("1mo", relative_to=date(2026, 2, 1)) == timedelta(days=28)
    ```
    """

@final
class CalendarSpan:
    def __new__(cls, text: str, /) -> CalendarSpan:
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
        from chronosapien import CalendarSpan

        span = CalendarSpan("1mo 2d")
        # Omitted units, such as hours here, read as zero.
        assert (span.months, span.days, span.hours) == (1, 2, 0)

        span = CalendarSpan("90m")
        # The span keeps all 90 minutes in the minutes field.
        assert (span.minutes, span.hours) == (90, 0)
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

        from chronosapien import CalendarSpan

        assert CalendarSpan("1d").to_timedelta() == timedelta(hours=24)

        month = CalendarSpan("1mo")
        # January 1 to February 1 is 31 days.
        assert month.to_timedelta(relative_to=date(2026, 1, 1)).days == 31
        # February 1 to March 1 is 28 days in 2026.
        assert month.to_timedelta(relative_to=date(2026, 2, 1)).days == 28
        ```
        """

    def total(
        self,
        unit: Literal[
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
        ],
        /,
        *,
        relative_to: date | None = None,
    ) -> float:
        """
        Return the span as a possibly fractional number of the given unit.

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

        from chronosapien import CalendarSpan

        assert CalendarSpan("90m").total("hour") == 1.5
        assert CalendarSpan("36h").total("day") == 1.5
        assert CalendarSpan("1mo").total("day", relative_to=date(2026, 2, 1)) == 28.0
        ```
        """

    def equivalent_to(
        self, other: CalendarSpan, /, *, relative_to: date | None = None
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
            If `other` is not a `CalendarSpan` or the reference has an unsupported
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

        from chronosapien import CalendarSpan

        assert CalendarSpan("1h").equivalent_to(CalendarSpan("60m"))
        assert CalendarSpan("1w").equivalent_to(CalendarSpan("168h"))

        month, days = CalendarSpan("1mo"), CalendarSpan("28d")
        # From February 1, both spans reach March 1.
        assert month.equivalent_to(days, relative_to=date(2026, 2, 1))
        # From January 1, reaching February 1 takes 31 days.
        assert not month.equivalent_to(days, relative_to=date(2026, 1, 1))
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

        from chronosapien import CalendarSpan

        start = datetime(2026, 1, 31, 9)
        # February 2026 has only 28 days, so the 31st becomes the 28th.
        assert CalendarSpan("1mo").add_to(start) == datetime(2026, 2, 28, 9)
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

        from chronosapien import CalendarSpan

        start = datetime(2026, 3, 31, 9)
        # Subtracting a month targets February, which ends on the 28th in 2026.
        assert CalendarSpan("1mo").subtract_from(start) == datetime(2026, 2, 28, 9)
        ```
        """

    def is_zero(self) -> bool:
        """Return whether every unit of the span is zero.

        Examples
        --------
        ```python
        from chronosapien import CalendarSpan

        assert CalendarSpan("0s").is_zero()
        ```
        """

    def is_positive(self) -> bool:
        """Return whether the span is strictly positive.

        Examples
        --------
        ```python
        from chronosapien import CalendarSpan

        assert CalendarSpan("1mo").is_positive()
        ```
        """

    def is_negative(self) -> bool:
        """Return whether the span is strictly negative.

        Examples
        --------
        ```python
        from chronosapien import CalendarSpan

        assert CalendarSpan("-2h").is_negative()
        ```
        """

    def abs(self) -> CalendarSpan:
        """Return the absolute value of the span.

        Examples
        --------
        ```python
        from chronosapien import CalendarSpan

        assert CalendarSpan("-2h").abs() == CalendarSpan("2h")
        ```
        """

    def negate(self) -> CalendarSpan:
        """Return a span with the opposite sign.

        Examples
        --------
        ```python
        from chronosapien import CalendarSpan

        assert CalendarSpan("2h").negate() == CalendarSpan("-2h")
        ```
        """

    def scale(self, n: int, /) -> CalendarSpan:
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
        from chronosapien import CalendarSpan

        scaled = CalendarSpan("50m").scale(2)
        # Doubling 50 minutes stores 100 in the minutes field.
        assert (scaled.hours, scaled.minutes) == (0, 100)
        ```
        """

    def __str__(self) -> str:
        """Format the span as an ISO 8601 duration.

        Examples
        --------
        ```python
        from chronosapien import CalendarSpan

        assert str(CalendarSpan("1mo 2d")) == "P1M2D"
        ```
        """

    def __repr__(self) -> str:
        """Return a constructor expression using Jiff's friendly format.

        Examples
        --------
        ```python
        from chronosapien import CalendarSpan

        assert repr(CalendarSpan("P1M2D")) == "CalendarSpan('1mo 2d')"
        ```
        """

    def to_friendly(self) -> str:
        """Return a human-readable duration string that preserves the stored units.

        Examples
        --------
        ```python
        from chronosapien import CalendarSpan

        assert CalendarSpan("P1M2D").to_friendly() == "1mo 2d"
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
        from chronosapien import CalendarSpan

        # Both spellings store one month and two days.
        assert CalendarSpan("P1M2D") == CalendarSpan("1mo 2d")
        # The first span stores 1 hour, and the second stores 60 minutes.
        assert CalendarSpan("1h") != CalendarSpan("60m")
        ```
        """

    def __hash__(self) -> int:
        """Return a hash based on the stored unit values.

        Examples
        --------
        ```python
        from chronosapien import CalendarSpan

        reminders = {CalendarSpan("1mo"): "renew subscription"}
        # The ISO 8601 spelling P1M produces the same dictionary key.
        assert reminders[CalendarSpan("P1M")] == "renew subscription"
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
