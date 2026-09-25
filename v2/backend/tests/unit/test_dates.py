from datetime import date

import pytest

from app.domain.normalizers import AmbiguousDate, DateError, ParsedDate, format_date, parse_date
from app.domain.parsing import Confirm, DateChoice, Parsed, Retry, parse_answer
from app.domain.registry import get_field
from tests.domain_helpers import REGION, TODAY

DOB = get_field("date_of_birth")
REFERRAL_DATE = get_field("referral_date")


@pytest.mark.parametrize(
    "raw",
    [
        "May 4th 2004",
        "May 4 2004",
        "May 4, 2004",
        "may 4, 2004",
        "4 May 2004",
        "4th of May 2004",
        "4th of May, 2004",
        "2004-05-04",
        "2004/5/4",
        "2004.05.04",
        "May  4   2004",
        "  May 4, 2004  ",
    ],
)
def test_unambiguous_formats_parse(raw: str) -> None:
    assert parse_date(raw) == ParsedDate(date(2004, 5, 4))


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("13/05/2004", date(2004, 5, 13)),  # 13 cannot be a month
        ("05/13/2004", date(2004, 5, 13)),
        ("7/7/2004", date(2004, 7, 7)),  # both readings are the same
        ("Sept 9 2004", date(2004, 9, 9)),
        ("dec 31 1999", date(1999, 12, 31)),
    ],
)
def test_numeric_dates_resolved_when_only_one_reading(raw: str, expected: date) -> None:
    assert parse_date(raw) == ParsedDate(expected)


def test_ambiguous_numeric_date_gives_both_readings() -> None:
    assert parse_date("04/05/2004") == AmbiguousDate(
        month_first=date(2004, 4, 5), day_first=date(2004, 5, 4)
    )


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        ("May 4", "date_needs_full_year"),
        ("04/05/04", "date_needs_full_year"),
        ("yesterday", "date_unreadable"),
        ("", "date_unreadable"),
        ("February 30 2004", "date_not_on_calendar"),
        ("2004-13-01", "date_not_on_calendar"),
        ("May 4 2004 5", "date_unreadable"),
    ],
)
def test_unreadable_dates_give_retry_codes(raw: str, code: str) -> None:
    assert parse_date(raw) == DateError(code)


def test_display_always_uses_month_word() -> None:
    assert format_date(date(2004, 5, 4)) == "May 4, 2004"


def test_ambiguous_date_field_offers_two_choices() -> None:
    result = parse_answer(DOB, "04/05/2004", today=TODAY, region=REGION)
    assert result == DateChoice(
        (Parsed("2004-04-05", "April 5, 2004"), Parsed("2004-05-04", "May 4, 2004"))
    )


def test_ambiguous_date_with_one_possible_reading_needs_confirmation() -> None:
    # 10/09/2026 reads as October 9 2026 (after TODAY) or September 10 2026 (before TODAY).
    result = parse_answer(DOB, "10/09/2026", today=TODAY, region=REGION)
    assert result == Confirm(Parsed("2026-09-10", "September 10, 2026"))


@pytest.mark.parametrize(
    ("field_id", "raw", "code"),
    [
        ("date_of_birth", "October 1 2026", "date_in_future"),
        ("date_of_birth", "May 4 1890", "date_too_long_ago"),
        ("referral_date", "May 4 2010", "date_too_long_ago"),
    ],
)
def test_date_range_checks(field_id: str, raw: str, code: str) -> None:
    assert parse_answer(get_field(field_id), raw, today=TODAY, region=REGION) == Retry(code)


def test_referral_date_today_is_accepted() -> None:
    result = parse_answer(REFERRAL_DATE, "September 26, 2026", today=TODAY, region=REGION)
    assert result == Parsed("2026-09-26", "September 26, 2026")
