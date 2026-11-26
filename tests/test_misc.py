from types import BuiltinFunctionType
from typing import cast

import chronosapien


def test_public_reexports() -> None:
    members = (
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

    assert chronosapien.__all__ == members
    assert dir(chronosapien) == list(members)
    for member in members:
        obj = cast(type[object] | BuiltinFunctionType, getattr(chronosapien, member))
        assert obj.__module__ == chronosapien.__name__
