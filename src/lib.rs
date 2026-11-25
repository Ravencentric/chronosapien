use pyo3::prelude::*;

pyo3::create_exception!(
    chronosapien,
    ChronosapienError,
    pyo3::exceptions::PyException
);
pyo3::create_exception!(chronosapien, SpanParseError, ChronosapienError);
pyo3::create_exception!(chronosapien, CalendarUnitError, ChronosapienError);
pyo3::create_exception!(chronosapien, InvalidUnitError, ChronosapienError);

#[pymodule]
mod chronosapien {
    use std::hash::{Hash, Hasher};

    use jiff::civil::{Date, DateTime};
    use jiff::{SignedDuration, Span, SpanRelativeTo, SpanRound, Unit, ZonedDateTime};
    use pyo3::exceptions::{PyOverflowError, PyTypeError, PyValueError};
    use pyo3::prelude::*;
    use pyo3::sync::PyOnceLock;
    use pyo3::types::{PyDate, PyDateTime, PyType, PyTzInfoAccess};

    #[pymodule_export]
    use super::{CalendarUnitError, ChronosapienError, InvalidUnitError, SpanParseError};

    #[pymodule_export]
    #[allow(non_upper_case_globals)]
    const __all__: (&str, &str, &str, &str, &str, &str) = (
        "CalendarUnitError",
        "ChronosapienError",
        "Duration",
        "InvalidUnitError",
        "SpanParseError",
        "to_timedelta",
    );

    // With no reference, Jiff's marker preserves 24-hour days and seven-day
    // weeks. Temporal's Duration.total likewise defaults to 24-hour days.
    // https://docs.rs/jiff/latest/jiff/struct.SpanRelativeTo.html#method.days_are_24_hours
    // https://tc39.es/proposal-temporal/#sec-temporal.duration.prototype.total
    #[pyfunction]
    #[pyo3(signature = (text, /, *, relative_to=None))]
    fn to_timedelta(
        text: &str,
        relative_to: Option<&Bound<'_, PyDate>>,
    ) -> PyResult<SignedDuration> {
        Duration::new(text)?.to_timedelta(relative_to)
    }

    #[pyclass(frozen, eq, hash, module = "chronosapien")]
    struct Duration {
        span: Span,
    }

    impl PartialEq for Duration {
        fn eq(&self, other: &Self) -> bool {
            self.span.fieldwise() == other.span.fieldwise()
        }
    }

    impl Eq for Duration {}

    impl Hash for Duration {
        fn hash<H: Hasher>(&self, state: &mut H) {
            self.span.fieldwise().hash(state);
        }
    }

    #[pymethods]
    impl Duration {
        #[new]
        #[pyo3(signature = (text, /))]
        fn new(text: &str) -> PyResult<Self> {
            Ok(Self {
                span: text
                    .parse::<Span>()
                    .map_err(|err| SpanParseError::new_err(err.to_string()))?,
            })
        }

        // Jiff's Span::to_duration accepts a date or the 24-hour-day marker.
        // Temporal's Duration.total also defaults to 24-hour days.
        // https://docs.rs/jiff/latest/jiff/struct.Span.html#method.to_duration
        // https://tc39.es/proposal-temporal/#sec-temporal.duration.prototype.total
        #[pyo3(signature = (*, relative_to=None))]
        fn to_timedelta(
            &self,
            relative_to: Option<&Bound<'_, PyDate>>,
        ) -> PyResult<SignedDuration> {
            with_span_reference(relative_to, |reference| self.span.to_duration(reference))
        }

        // Like Temporal's Duration.total, default to 24-hour days. Jiff's marker
        // also treats weeks as seven days when the span or target uses weeks.
        // https://docs.rs/jiff/latest/jiff/struct.Span.html#method.total
        // https://tc39.es/proposal-temporal/#sec-temporal.duration.prototype.total
        #[pyo3(signature = (unit, /, *, relative_to=None))]
        fn total(&self, unit: &str, relative_to: Option<&Bound<'_, PyDate>>) -> PyResult<f64> {
            let unit = parse_unit(unit)?;
            with_span_reference(relative_to, |reference| self.span.total((unit, reference)))
        }

        // Jiff's Span::round and Temporal's Duration.round default to rounding
        // ties away from zero. Jiff's marker also supports unanchored weeks.
        // https://docs.rs/jiff/latest/jiff/struct.Span.html#method.round
        // https://tc39.es/proposal-temporal/#sec-temporal.duration.prototype.round
        #[pyo3(signature = (*, largest, smallest="nanosecond", relative_to=None))]
        fn round(
            &self,
            largest: &str,
            smallest: &str,
            relative_to: Option<&Bound<'_, PyDate>>,
        ) -> PyResult<Self> {
            let largest = parse_unit(largest)?;
            let smallest = parse_unit(smallest)?;
            if largest < smallest {
                return Err(InvalidUnitError::new_err(
                    "largest must be at least as large as smallest.",
                ));
            }

            let options = SpanRound::new().largest(largest).smallest(smallest);
            let span = if relative_to.is_some() {
                with_span_reference(relative_to, |reference| {
                    self.span.round(options.relative(reference))
                })?
            } else {
                if largest >= Unit::Month
                    || self.span.get_years() != 0
                    || self.span.get_months() != 0
                {
                    return Err(missing_span_reference());
                }
                self.span.round(options.days_are_24_hours())?
            };
            Ok(Self { span })
        }

        // Like Temporal's Duration.compare, compare unanchored days as 24 hours.
        // Jiff's marker also treats a week in either span as seven days.
        // https://docs.rs/jiff/latest/jiff/struct.Span.html#method.compare
        // https://tc39.es/proposal-temporal/#sec-temporal.duration.compare
        #[pyo3(signature = (other, /, *, relative_to=None))]
        fn equivalent_to(
            &self,
            other: &Self,
            relative_to: Option<&Bound<'_, PyDate>>,
        ) -> PyResult<bool> {
            with_span_reference(relative_to, |reference| {
                self.span
                    .compare((other.span, reference))
                    .map(std::cmp::Ordering::is_eq)
            })
        }

        fn add_to<'py>(&self, start: &Bound<'py, PyDateTime>) -> PyResult<Bound<'py, PyDateTime>> {
            let py = start.py();
            match ReferenceDateTime::from_python(start)? {
                ReferenceDateTime::Naive(datetime) => {
                    datetime.checked_add(self.span)?.into_pyobject(py)
                }
                ReferenceDateTime::Aware(datetime) => {
                    datetime.checked_add(self.span)?.into_pyobject(py)
                }
            }
        }

        fn subtract_from<'py>(
            &self,
            start: &Bound<'py, PyDateTime>,
        ) -> PyResult<Bound<'py, PyDateTime>> {
            let py = start.py();
            match ReferenceDateTime::from_python(start)? {
                ReferenceDateTime::Naive(datetime) => {
                    datetime.checked_sub(self.span)?.into_pyobject(py)
                }
                ReferenceDateTime::Aware(datetime) => {
                    datetime.checked_sub(self.span)?.into_pyobject(py)
                }
            }
        }

        fn is_zero(&self) -> bool {
            self.span.is_zero()
        }

        fn is_positive(&self) -> bool {
            self.span.is_positive()
        }

        fn is_negative(&self) -> bool {
            self.span.is_negative()
        }

        fn abs(&self) -> Self {
            Self {
                span: self.span.abs(),
            }
        }

        fn negate(&self) -> Self {
            Self {
                span: self.span.negate(),
            }
        }

        #[pyo3(signature = (n, /))]
        fn scale(&self, n: i64) -> PyResult<Self> {
            let span = self
                .span
                .checked_mul(n)
                .map_err(|err| PyOverflowError::new_err(err.to_string()))?;
            Ok(Self { span })
        }

        fn __str__(&self) -> String {
            self.span.to_string()
        }

        fn __repr__(&self) -> String {
            format!("Duration('{}')", self.to_friendly())
        }

        fn to_friendly(&self) -> String {
            self.span.to_friendly()
        }

        #[getter]
        fn years(&self) -> i16 {
            self.span.get_years()
        }

        #[getter]
        fn months(&self) -> i32 {
            self.span.get_months()
        }

        #[getter]
        fn weeks(&self) -> i32 {
            self.span.get_weeks()
        }

        #[getter]
        fn days(&self) -> i32 {
            self.span.get_days()
        }

        #[getter]
        fn hours(&self) -> i32 {
            self.span.get_hours()
        }

        #[getter]
        fn minutes(&self) -> i64 {
            self.span.get_minutes()
        }

        #[getter]
        fn seconds(&self) -> i64 {
            self.span.get_seconds()
        }

        #[getter]
        fn milliseconds(&self) -> i64 {
            self.span.get_milliseconds()
        }

        #[getter]
        fn microseconds(&self) -> i64 {
            self.span.get_microseconds()
        }

        #[getter]
        fn nanoseconds(&self) -> i64 {
            self.span.get_nanoseconds()
        }
    }

    fn parse_unit(unit: &str) -> PyResult<Unit> {
        let unit = match unit {
            "year" => Unit::Year,
            "month" => Unit::Month,
            "week" => Unit::Week,
            "day" => Unit::Day,
            "hour" => Unit::Hour,
            "minute" => Unit::Minute,
            "second" => Unit::Second,
            "millisecond" => Unit::Millisecond,
            "microsecond" => Unit::Microsecond,
            "nanosecond" => Unit::Nanosecond,
            _ => return Err(InvalidUnitError::new_err(format!("unknown unit: {unit:?}"))),
        };
        Ok(unit)
    }

    fn missing_span_reference() -> PyErr {
        CalendarUnitError::new_err(
            "relative_to is required for years or months. Pass a date or datetime.",
        )
    }

    fn with_span_reference<T>(
        relative_to: Option<&Bound<'_, PyDate>>,
        operation: impl FnOnce(SpanRelativeTo<'_>) -> Result<T, jiff::Error>,
    ) -> PyResult<T> {
        let Some(relative_to) = relative_to else {
            return operation(SpanRelativeTo::days_are_24_hours())
                .map_err(|_| missing_span_reference());
        };
        let result = if let Ok(datetime) = relative_to.cast::<PyDateTime>() {
            match ReferenceDateTime::from_python(datetime)? {
                ReferenceDateTime::Naive(datetime) => operation(datetime.into()),
                ReferenceDateTime::Aware(datetime) => operation((&datetime).into()),
            }
        } else {
            operation(relative_to.extract::<Date>()?.into())
        };
        Ok(result?)
    }

    enum ReferenceDateTime {
        // dt.datetime(2024, 3, 10, 0, 0)
        Naive(DateTime),
        // dt.datetime(2024, 3, 10, 0, 0, tzinfo=dt.timezone(dt.timedelta(hours=-5)))
        // dt.datetime(2024, 3, 10, 0, 0, tzinfo=ZoneInfo("America/New_York"))
        Aware(ZonedDateTime),
    }

    impl ReferenceDateTime {
        fn from_python(datetime: &Bound<'_, PyDateTime>) -> PyResult<Self> {
            let Some(timezone) = datetime.get_tzinfo() else {
                // no timezone
                return Ok(Self::Naive(datetime.extract()?));
            };
            let py = datetime.py();

            // Time zone is a fixed offset:
            // datetime(2024, 3, 10, 0, 0, tzinfo=timezone(timedelta(hours=-5)))
            static FIXED_OFFSET_TYPE: PyOnceLock<Py<PyType>> = PyOnceLock::new();
            let fixed_offset_type = FIXED_OFFSET_TYPE.import(py, "datetime", "timezone")?;
            if timezone.is_instance(fixed_offset_type)? {
                return Ok(Self::Aware(datetime.extract()?));
            }

            // Time zone is a named zoneinfo object:
            // datetime(2024, 3, 10, 0, 0, tzinfo=ZoneInfo("America/New_York"))
            static ZONEINFO_TYPE: PyOnceLock<Py<PyType>> = PyOnceLock::new();
            let zoneinfo_type = ZONEINFO_TYPE.import(py, "zoneinfo", "ZoneInfo")?;
            if !timezone.is_instance(zoneinfo_type)? {
                return Err(PyTypeError::new_err(
                    "expected a naive datetime or datetime with datetime.timezone or zoneinfo.ZoneInfo",
                ));
            }
            // https://docs.python.org/3/library/zoneinfo.html#zoneinfo.ZoneInfo.key
            if timezone.getattr(pyo3::intern!(py, "key"))?.is_none() {
                return Err(PyValueError::new_err("ZoneInfo must have an IANA key"));
            }
            Ok(Self::Aware(datetime.extract()?))
        }
    }
}
