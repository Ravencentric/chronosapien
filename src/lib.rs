use pyo3::prelude::*;

pyo3::create_exception!(
    chronosapien,
    ChronosapienError,
    pyo3::exceptions::PyException
);
pyo3::create_exception!(chronosapien, SpanParseError, ChronosapienError);
pyo3::create_exception!(chronosapien, CalendarUnitError, ChronosapienError);
pyo3::create_exception!(chronosapien, DurationFormatError, ChronosapienError);
pyo3::create_exception!(chronosapien, InvalidUnitError, ChronosapienError);

#[pymodule]
mod chronosapien {
    use std::hash::{Hash, Hasher};

    use jiff::civil::{Date, DateTime};
    use jiff::fmt::friendly::{Designator, Direction, FractionalUnit, Spacing, SpanPrinter};
    use jiff::{
        SignedDuration, Span, SpanArithmetic, SpanRelativeTo, SpanRound, Unit, ZonedDateTime,
    };
    use pyo3::exceptions::{PyOverflowError, PyTypeError, PyValueError};
    use pyo3::prelude::*;
    use pyo3::sync::PyOnceLock;
    use pyo3::types::{PyDate, PyDateTime, PyType, PyTzInfoAccess};

    #[pymodule_export]
    use super::{
        CalendarUnitError, ChronosapienError, DurationFormatError, InvalidUnitError, SpanParseError,
    };

    #[pymodule_export]
    #[allow(non_upper_case_globals)]
    const __all__: (&str, &str, &str, &str, &str, &str, &str, &str) = (
        "CalendarUnitError",
        "ChronosapienError",
        "Duration",
        "DurationFormatError",
        "DurationFormatter",
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

    impl Duration {
        fn span_arithmetic(
            &self,
            other: &Self,
            relative_to: Option<&Bound<'_, PyDate>>,
            operation: impl FnOnce(SpanArithmetic<'_>) -> Result<Span, jiff::Error>,
        ) -> PyResult<Self> {
            let span = if relative_to.is_some() {
                with_span_reference(relative_to, |reference| {
                    operation((other.span, reference).into())
                })?
            } else {
                if [self, other]
                    .into_iter()
                    .any(|duration| duration.years() != 0 || duration.months() != 0)
                {
                    return Err(missing_span_reference());
                }
                operation(SpanArithmetic::from(other.span).days_are_24_hours())?
            };
            Ok(Self { span })
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

        // Keep timedelta days as fixed elapsed seconds across offset changes.
        // https://docs.rs/jiff/latest/jiff/struct.Span.html#impl-TryFrom%3CSignedDuration%3E-for-Span
        #[staticmethod]
        #[pyo3(signature = (delta, /))]
        fn from_timedelta(delta: SignedDuration) -> PyResult<Self> {
            let span =
                Span::try_from(delta).map_err(|err| PyOverflowError::new_err(err.to_string()))?;
            Ok(Self { span })
        }

        #[staticmethod]
        #[pyo3(signature = (start, end, /, *, largest=None))]
        fn between(
            start: &Bound<'_, PyDate>,
            end: &Bound<'_, PyDate>,
            largest: Option<&str>,
        ) -> PyResult<Self> {
            let largest = largest.map(parse_unit).transpose()?;
            let (start, end) = match (start.cast::<PyDateTime>(), end.cast::<PyDateTime>()) {
                (Ok(start), Ok(end)) => (start, end),
                (Err(_), Err(_)) => {
                    let start = start.extract::<Date>()?;
                    let end = end.extract::<Date>()?;
                    let span = match largest {
                        Some(largest) => start.until((largest, end)),
                        None => start.until(end),
                    }?;
                    return Ok(Self { span });
                }
                _ => {
                    return Err(PyTypeError::new_err(
                        "start and end must both be dates or both be datetimes",
                    ));
                }
            };
            let span = match (
                ReferenceDateTime::from_python(start)?,
                ReferenceDateTime::from_python(end)?,
            ) {
                (ReferenceDateTime::Naive(start), ReferenceDateTime::Naive(end)) => match largest {
                    Some(largest) => start.until((largest, end))?,
                    None => start.until(end)?,
                },
                (ReferenceDateTime::Aware(start), ReferenceDateTime::Aware(end)) => match largest {
                    Some(largest) => start.until((largest, &end))?,
                    None => start.until(&end)?,
                },
                _ => {
                    return Err(PyTypeError::new_err(
                        "start and end must both be naive or both be aware datetimes",
                    ));
                }
            };
            Ok(Self { span })
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

        #[pyo3(signature = (other, /, *, relative_to=None))]
        fn plus(&self, other: &Self, relative_to: Option<&Bound<'_, PyDate>>) -> PyResult<Self> {
            self.span_arithmetic(other, relative_to, |options| self.span.checked_add(options))
        }

        #[pyo3(signature = (other, /, *, relative_to=None))]
        fn minus(&self, other: &Self, relative_to: Option<&Bound<'_, PyDate>>) -> PyResult<Self> {
            self.span_arithmetic(other, relative_to, |options| self.span.checked_sub(options))
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
            format!("Duration('{}')", self.span.to_friendly())
        }

        #[pyo3(signature = (
            *,
            designator="compact",
            spacing="auto",
            comma=None,
            direction="auto",
            hhmmss=false,
            fractional=None,
            precision=None,
            padding=None,
        ))]
        #[expect(
            clippy::too_many_arguments,
            reason = "Python keyword-only printer options"
        )]
        fn to_friendly(
            &self,
            designator: &str,
            spacing: &str,
            comma: Option<bool>,
            direction: &str,
            hhmmss: bool,
            fractional: Option<&str>,
            precision: Option<u8>,
            padding: Option<u8>,
        ) -> PyResult<String> {
            let formatter = DurationFormatter::new(
                designator, spacing, comma, direction, hhmmss, fractional, precision, padding,
            )?;
            Ok(formatter.format(self))
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

    #[pyclass(frozen, module = "chronosapien")]
    struct DurationFormatter {
        printer: SpanPrinter,
    }

    #[pymethods]
    impl DurationFormatter {
        #[new]
        #[pyo3(signature = (
            *,
            designator="compact",
            spacing="auto",
            comma=None,
            direction="auto",
            hhmmss=false,
            fractional=None,
            precision=None,
            padding=None,
        ))]
        #[expect(
            clippy::too_many_arguments,
            reason = "Python keyword-only printer options"
        )]
        fn new(
            designator: &str,
            spacing: &str,
            comma: Option<bool>,
            direction: &str,
            hhmmss: bool,
            fractional: Option<&str>,
            precision: Option<u8>,
            padding: Option<u8>,
        ) -> PyResult<Self> {
            let designator = match designator {
                "compact" => Designator::Compact,
                "short" => Designator::Short,
                "verbose" => Designator::Verbose,
                _ => {
                    return Err(DurationFormatError::new_err(format!(
                        "unknown friendly designator: {designator:?}"
                    )));
                }
            };
            let spacing = match spacing {
                // map "auto" to None because
                // an API like `spacing: None | "none" | "units"`
                // is much more confusing on the Python side.
                "auto" => None,
                "none" => Some(Spacing::None),
                "units" => Some(Spacing::BetweenUnits),
                "designators" => Some(Spacing::BetweenUnitsAndDesignators),
                _ => {
                    return Err(DurationFormatError::new_err(format!(
                        "unknown friendly spacing: {spacing:?}"
                    )));
                }
            };
            let fractional = match fractional {
                None => None,
                Some("hour") => Some(FractionalUnit::Hour),
                Some("minute") => Some(FractionalUnit::Minute),
                Some("second") => Some(FractionalUnit::Second),
                Some("millisecond") => Some(FractionalUnit::Millisecond),
                Some("microsecond") => Some(FractionalUnit::Microsecond),
                Some(unit) => {
                    return Err(DurationFormatError::new_err(format!(
                        "unknown fractional unit: {unit:?}"
                    )));
                }
            };
            let direction = match direction {
                "auto" => Direction::Auto,
                "sign" => Direction::Sign,
                "suffix" => Direction::Suffix,
                _ => {
                    return Err(DurationFormatError::new_err(format!(
                        "unknown friendly direction: {direction:?}"
                    )));
                }
            };
            let mut printer = SpanPrinter::new()
                .designator(designator)
                .hours_minutes_seconds(hhmmss)
                .direction(direction)
                .fractional(fractional);
            if let Some(spacing) = spacing {
                printer = printer.spacing(spacing);
            }
            if let Some(comma) = comma {
                printer = printer.comma_after_designator(comma);
            }

            printer = match precision {
                Some(p) if p > 9 => {
                    return Err(DurationFormatError::new_err(format!(
                        "unsupported friendly precision: {p}. Expected a number between 0 and 9."
                    )));
                }
                p => printer.precision(p),
            };

            printer = match padding {
                Some(p) if p > 20 => {
                    return Err(DurationFormatError::new_err(format!(
                        "unsupported friendly padding: {p}. Expected a number between 0 and 20."
                    )));
                }
                Some(p) => printer.padding(p),
                None => printer,
            };

            Ok(Self { printer })
        }

        #[pyo3(signature = (duration, /))]
        fn format(&self, duration: &Duration) -> String {
            self.printer.span_to_string(&duration.span)
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
