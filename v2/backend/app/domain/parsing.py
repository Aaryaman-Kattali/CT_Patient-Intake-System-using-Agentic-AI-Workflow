"""Turn a raw reply for one field into a validated value, a date choice, or a retry code.

This is the only way a value reaches storage. The stored value always comes from here,
never from the LLM (docs/V2_SPEC.md §6.3).
"""

from dataclasses import dataclass
from datetime import date

from app.domain.fields import FieldDef, Option
from app.domain.normalizers import (
    AmbiguousDate,
    DateError,
    format_date,
    format_phone,
    match_key,
    normalize_email,
    normalize_phone,
    normalize_text,
    parse_date,
)
from app.domain.types import InputType

MAX_TEXT_CHARS = 200
MAX_NAME_CHARS = 100
MAX_AGE_YEARS = 130
MAX_REFERRAL_AGE_YEARS = 10


@dataclass(frozen=True)
class Parsed:
    value: str  # canonical, stored (ISO date, E.164 phone, option id, text)
    display: str  # shown back to the user
    extra_text: str | None = None


@dataclass(frozen=True)
class DateChoice:
    choices: tuple[Parsed, Parsed]


@dataclass(frozen=True)
class Confirm:
    """Only one reading of an ambiguous date is possible. Never accept it silently:
    the workflow asks a yes/no question with this value."""

    value: Parsed


@dataclass(frozen=True)
class Retry:
    code: str  # key into templates.RETRY


ParseResult = Parsed | DateChoice | Confirm | Retry


def parse_answer(field: FieldDef, raw: str, *, today: date, region: str) -> ParseResult:
    """Parse typed text for a non-choice field."""
    match field.input_type:
        case InputType.DATE:
            return _parse_date_field(field, raw, today)
        case InputType.PHONE:
            phone = normalize_phone(raw, region)
            return (
                Parsed(phone, format_phone(phone, region)) if phone else Retry("phone_unreadable")
            )
        case InputType.EMAIL:
            email = normalize_email(raw)
            return Parsed(email, email) if email else Retry("email_unreadable")
        case InputType.TEXT:
            return _parse_text_field(field, raw)
        case InputType.CHOICE:
            option = match_option(field, raw)
            if option is None or option.free_text:
                return Retry("choose_option")
            return Parsed(option.id, option.label)


def parse_choice(field: FieldDef, option_id: str, extra_text: str | None = None) -> ParseResult:
    """Parse a button press (plus the text box for free_text options)."""
    option = field.option(option_id)
    if option is None:
        return Retry("choose_option")
    if not option.free_text:
        return Parsed(option.id, option.label)
    text = normalize_text(extra_text or "")
    if not text:
        return Retry("type_a_few_words")
    if len(text) > MAX_TEXT_CHARS:
        return Retry("text_too_long")
    return Parsed(option.id, text, extra_text=text)


def match_option(field: FieldDef, raw: str) -> Option | None:
    """Exact label or id match, ignoring case and punctuation. Anything fuzzier is the LLM's
    job and is then marked `inferred`, which always needs a yes/no confirmation."""
    key = match_key(raw)
    return next((o for o in field.options if key in (match_key(o.label), match_key(o.id))), None)


def _parse_date_field(field: FieldDef, raw: str, today: date) -> ParseResult:
    result = parse_date(raw)
    if isinstance(result, DateError):
        return Retry(result.code)
    if isinstance(result, AmbiguousDate):
        valid = [
            d for d in (result.month_first, result.day_first) if not _date_error(field, d, today)
        ]
        if len(valid) == 1:  # the other reading is impossible, e.g. in the future
            return Confirm(Parsed(valid[0].isoformat(), format_date(valid[0])))
        if not valid:
            return Retry(_date_error(field, result.month_first, today) or "date_unreadable")
        first, second = (Parsed(d.isoformat(), format_date(d)) for d in valid)
        return DateChoice((first, second))
    error = _date_error(field, result.value, today)
    return Retry(error) if error else Parsed(result.value.isoformat(), format_date(result.value))


def _date_error(field: FieldDef, value: date, today: date) -> str | None:
    if value > today:
        return "date_in_future"
    max_years = MAX_REFERRAL_AGE_YEARS if field.id == "referral_date" else MAX_AGE_YEARS
    if value.year < today.year - max_years:
        return "date_too_long_ago"
    return None


def _parse_text_field(field: FieldDef, raw: str) -> ParseResult:
    text = normalize_text(raw)
    limit = MAX_NAME_CHARS if field.id.endswith("name") else MAX_TEXT_CHARS
    if not any(ch.isalpha() for ch in text):
        return Retry("text_needs_letters")
    if len(text) > limit:
        return Retry("text_too_long")
    if field.id == "address" and len(text) < 5:
        return Retry("address_too_short")
    return Parsed(text, text)
