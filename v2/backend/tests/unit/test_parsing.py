import pytest

from app.domain.normalizers import match_yes_no, normalize_email, normalize_phone, normalize_text
from app.domain.parsing import Parsed, Retry, match_option, parse_answer, parse_choice
from app.domain.registry import get_field
from tests.domain_helpers import REGION, TODAY


def _parse(field_id: str, raw: str) -> object:
    return parse_answer(get_field(field_id), raw, today=TODAY, region=REGION)


# --- phone -------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    ["202-555-0100", "(202) 555-0100", "202.555.0100", "2025550100", "+1 202 555 0100"],
)
def test_phone_formats_normalize_to_e164(raw: str) -> None:
    assert normalize_phone(raw, REGION) == "+12025550100"


@pytest.mark.parametrize("raw", ["555-0100", "12345", "202-555-01000", "call me", ""])
def test_unreadable_phone_is_rejected(raw: str) -> None:
    assert normalize_phone(raw, REGION) is None
    assert _parse("phone", raw) == Retry("phone_unreadable")


def test_phone_is_shown_back_in_national_format() -> None:
    assert _parse("phone", "2025550143") == Parsed("+12025550143", "(202) 555-0143")


# --- email -------------------------------------------------------------------


def test_email_domain_is_lower_cased() -> None:
    assert normalize_email("Alex@Example.COM") == "Alex@example.com"


@pytest.mark.parametrize("raw", ["alex@", "alex example.com", "a b@example.com", ""])
def test_unreadable_email_is_rejected(raw: str) -> None:
    assert _parse("email", raw) == Retry("email_unreadable")


# --- text --------------------------------------------------------------------


def test_text_is_trimmed_and_whitespace_collapsed() -> None:
    assert _parse("full_name", "  Alex   Rivera \n") == Parsed("Alex Rivera", "Alex Rivera")


def test_control_characters_are_removed() -> None:
    assert normalize_text("Alex\x00\x07 Rivera") == "Alex Rivera"


@pytest.mark.parametrize(
    ("field_id", "raw", "code"),
    [
        ("full_name", "12345", "text_needs_letters"),
        ("full_name", "   ", "text_needs_letters"),
        ("full_name", "A" * 101, "text_too_long"),
        ("address", "Oak", "address_too_short"),
    ],
)
def test_text_validation(field_id: str, raw: str, code: str) -> None:
    assert _parse(field_id, raw) == Retry(code)


# --- choices -----------------------------------------------------------------


@pytest.mark.parametrize("raw", ["My child", "my child", "MY CHILD.", "child"])
def test_exact_option_label_or_id_matches(raw: str) -> None:
    option = match_option(get_field("relationship"), raw)
    assert option is not None
    assert option.id == "child"


def test_fuzzy_option_text_is_left_to_the_llm() -> None:
    assert match_option(get_field("relationship"), "my son") is None
    assert _parse("relationship", "my son") == Retry("choose_option")


def test_button_choice_parses_to_option_id() -> None:
    assert parse_choice(get_field("relationship"), "child") == Parsed("child", "My child")


def test_unknown_button_choice_is_rejected() -> None:
    assert parse_choice(get_field("relationship"), "stranger") == Retry("choose_option")


def test_free_text_option_keeps_typed_words_verbatim() -> None:
    result = parse_choice(get_field("inquiry_reason"), "something_else", "  Sleep  help ")
    assert result == Parsed("something_else", "Sleep help", extra_text="Sleep help")


def test_free_text_option_needs_words() -> None:
    assert parse_choice(get_field("gender"), "another", "  ") == Retry("type_a_few_words")


def test_free_text_option_cannot_be_matched_from_typed_text() -> None:
    assert _parse("inquiry_reason", "Something else (type it)") == Retry("choose_option")


# --- yes / no ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("yes", True),
        ("Yes.", True),
        ("yep", True),
        ("That's right", True),
        ("no", False),
        ("Nope!", False),
        ("not right", False),
        ("maybe", None),
        ("yes but my name is Sam", None),
    ],
)
def test_yes_no_matcher(raw: str, expected: bool | None) -> None:
    assert match_yes_no(raw) is expected
