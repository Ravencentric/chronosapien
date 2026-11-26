from . import chronosapien as _native
from .chronosapien import *

__all__ = _native.__all__
__doc__ = _native.__doc__
_native.to_timedelta.__module__ = __name__


def __dir__() -> list[str]:
    return list(__all__)
