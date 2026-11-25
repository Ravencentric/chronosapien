# chronosapien

`chronosapien` parses human-readable and [ISO 8601](https://en.wikipedia.org/wiki/ISO_8601#Durations)
duration (and duration strings only) strings using [Jiff](https://docs.rs/jiff/latest/jiff/).

## Usage

```python
from datetime import timedelta

from chronosapien import Duration, to_timedelta

elapsed = to_timedelta("2 hours, 30 minutes")
assert elapsed == timedelta(hours=2, minutes=30)
assert to_timedelta("PT2H30M") == elapsed

offset = to_timedelta("2 hours, 30 minutes ago")
assert offset == -timedelta(hours=2, minutes=30)

span = Duration("1 month, 2 days, 3 hours")
assert span.months == 1
assert span.days == 2
assert span.hours == 3

assert Duration("1mo, 2 days 3h") == span
assert Duration("P1M2DT3H") == span
```

These inputs come from [Jiff's friendly-format examples](https://docs.rs/jiff/latest/jiff/fmt/friendly/index.html).

| Input                         | `Duration(text).to_friendly()`     |
|-------------------------------|------------------------------------|
| `40d` or `40 days`            | `40d`                              |
| `2h30m`                       | `2h 30m`                           |
| `3 days, 4 hours, 59 minutes` | `3d 4h 59m`                        |
| `1 wk 4 days`                 | `1w 4d`                            |
| `1yr 1d`                      | `1y 1d`                            |
| `3 mins 34,123s`              | `3m 34s 123ms`                     |
| `2 months, 35 days, 02:30:00` | `2mo 35d 2h 30m`                   |

See the API docs for [`to_timedelta()`](https://ravencentri.cc/chronosapien/reference/to-timedelta/)
and [`Duration`](https://ravencentri.cc/chronosapien/reference/duration/).

## Installation

`chronosapien` requires Python 3.11 or newer. Install it from [PyPI](https://pypi.org/project/chronosapien/).

```sh
pip install chronosapien
```

## Building from source

Building from source requires the [Rust toolchain](https://rustup.rs/) and [Python 3.11+](https://www.python.org/downloads/).

- With [`uv`](https://docs.astral.sh/uv/):

  ```console
  git clone https://github.com/Ravencentric/chronosapien
  cd chronosapien
  uv build
  ```

- With [`pypa/build`](https://github.com/pypa/build):

  ```console
  git clone https://github.com/Ravencentric/chronosapien
  cd chronosapien
  python -m build
  ```

## Acknowledgements

This project is essentially a thin wrapper around the excellent [`Jiff`](https://crates.io/crates/jiff) crate by [BurntSushi](https://github.com/BurntSushi/jiff).

## License

Distributed under the [Mozilla Public License 2.0](https://www.mozilla.org/MPL/2.0/). See [LICENSE](https://github.com/Ravencentric/chronosapien/blob/main/LICENSE) for more information.
