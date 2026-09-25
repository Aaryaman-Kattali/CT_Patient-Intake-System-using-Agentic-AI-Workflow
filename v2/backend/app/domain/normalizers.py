"""Turn what people type into canonical values. Formats are the system's job, not the user's.

Everything here is deterministic. No guessing: a date that could mean two things is returned
as AmbiguousDate so the workflow can ask with two buttons.
"""

import re
import unicodedata
from dataclasses import dataclass
from datetime import date

import phonenumbers
from email_validator import EmailNotValidError, validate_email

MONTHS = {
    name: number
    for number, names in enumerate(
        [
            ("january", "jan"),
            ("february", "feb"),
            ("march", "mar"),
            ("april", "apr"),
            ("may",),
            ("june", "jun"),
            ("july", "jul"),
            ("august", "aug"),
            ("september", "sep", "sept"),
            ("october", "oct"),
            ("november", "nov"),
            ("december", "dec"),
        ],
        start=1,
    )
    for name in names
}
MONTH_NAMES = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]

_ORDINAL = re.compile(r"\b(\d{1,2})(st|nd|rd|th)\b")
_SEPARATORS = re.compile(r"[\s,./-]+")


@dataclass(frozen=True)
class ParsedDate:
    value: date


@dataclass(frozen=True)
class AmbiguousDate:
    month_first: date  # 04/05/2004 -> April 5
    day_first: date  # 04/05/2004 -> May 4


@dataclass(frozen=True)
class DateError:
    code: str  # key into templates.RETRY


DateResult = ParsedDate | AmbiguousDate | DateError


def normalize_text(raw: str) -> str:
    """NFKC, strip control characters, collapse whitespace."""
    text = unicodedata.normalize("NFKC", raw)
    text = "".join(ch for ch in text if unicodedata.category(ch)[0] != "C" or ch in " \t\n")
    return " ".join(text.split())


def parse_date(raw: str) -> DateResult:
    text = _ORDINAL.sub(r"\1", normalize_text(raw).lower())
    tokens = [t for t in _SEPARATORS.split(text) if t and t != "of"]
    if len(tokens) == 2 and any(t in MONTHS for t in tokens):
        return DateError("date_needs_full_year")  # "May 4": never fill in a year
    if len(tokens) != 3:
        return DateError("date_unreadable")
    if any(t in MONTHS for t in tokens):
        return _parse_named_month(tokens)
    if all(t.isdigit() for t in tokens):
        return _parse_numeric(tokens)
    return DateError("date_unreadable")


def _parse_named_month(tokens: list[str]) -> DateResult:
    month_index = next(i for i, t in enumerate(tokens) if t in MONTHS)
    others = [t for i, t in enumerate(tokens) if i != month_index]
    if not all(t.isdigit() for t in others):
        return DateError("date_unreadable")
    years = [t for t in others if len(t) == 4]
    days = [t for t in others if len(t) <= 2]
    if len(years) != 1 or len(days) != 1:
        return DateError("date_needs_full_year")
    return _make(int(years[0]), MONTHS[tokens[month_index]], int(days[0]))


def _parse_numeric(tokens: list[str]) -> DateResult:
    first, second, third = tokens
    if len(first) == 4:  # 2004-05-04: year first is always year-month-day
        return _make(int(first), int(second), int(third))
    if len(third) != 4:
        return DateError("date_needs_full_year")
    a, b, year = int(first), int(second), int(third)
    if a > 12 and b <= 12:
        return _make(year, b, a)
    if b > 12 and a <= 12:
        return _make(year, a, b)
    if a == b:
        return _make(year, a, b)
    month_first, day_first = _make(year, a, b), _make(year, b, a)
    if isinstance(month_first, ParsedDate) and isinstance(day_first, ParsedDate):
        return AmbiguousDate(month_first=month_first.value, day_first=day_first.value)
    return DateError("date_not_on_calendar")


def _make(year: int, month: int, day: int) -> DateResult:
    try:
        return ParsedDate(date(year, month, day))
    except ValueError:
        return DateError("date_not_on_calendar")


def format_date(value: date) -> str:
    """Always show the month as a word, so the reading is never ambiguous."""
    return f"{MONTH_NAMES[value.month - 1]} {value.day}, {value.year}"


def normalize_phone(raw: str, region: str) -> str | None:
    """Return E.164 (e.g. +12025550100), or None if it is not a valid number."""
    try:
        number = phonenumbers.parse(normalize_text(raw), region)
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_valid_number(number):
        return None
    return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)


def format_phone(e164: str, region: str) -> str:
    number = phonenumbers.parse(e164, None)
    if phonenumbers.region_code_for_number(number) == region:
        return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.NATIONAL)
    return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.INTERNATIONAL)


def normalize_email(raw: str) -> str | None:
    try:
        result = validate_email(normalize_text(raw), check_deliverability=False)
    except EmailNotValidError:
        return None
    return result.normalized


_WORDS = re.compile(r"[a-z0-9]+")


def match_key(text: str) -> tuple[str, ...]:
    return tuple(_WORDS.findall(normalize_text(text).lower().replace("'", "")))


YES = frozenset(
    {("yes",), ("y",), ("yeah",), ("yep",), ("correct",), ("thats", "right"), ("right",)}
)
NO = frozenset({("no",), ("n",), ("nope",), ("not", "right"), ("thats", "wrong"), ("wrong",)})


def match_yes_no(raw: str) -> bool | None:
    """Deterministic yes/no for typed confirmations. None means "ask the LLM"."""
    key = match_key(raw)
    if key in YES:
        return True
    if key in NO:
        return False
    return None
