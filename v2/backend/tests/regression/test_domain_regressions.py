"""Named regression tests for audit items and owner decisions that live in the domain layer.

Workflow- and API-level versions of some of these (e.g. submit through the engine) are
added in Phases 4 and 6.
"""

from datetime import date

import pytest

from app.domain import templates as t
from app.domain.clinical import CONDITION_CLAIMS
from app.domain.normalizers import normalize_phone
from app.domain.parsing import DateChoice, Parsed, parse_answer
from app.domain.registry import FIELDS, get_field
from app.domain.requirements import (
    ABOUT_TOTAL,
    can_mark_unknown,
    can_submit,
    is_applicable,
    is_needed,
    missing_must_have,
    next_field,
    not_sure_outcome,
    path_total,
    review_items,
)
from app.domain.types import FieldStatus, IntakeType
from app.domain.wording import is_about_respondent, question_text
from tests.domain_helpers import REGION, TODAY, build

FI, PR = IntakeType.FAMILY_INQUIRY.value, IntakeType.PROVIDER_REFERRAL.value
D, DK, UNKNOWN = FieldStatus.DEFERRED, FieldStatus.DONT_KNOW, FieldStatus.UNKNOWN_CONFIRMED
SKIP = FieldStatus.SKIPPED
CONTACT = ("phone", "email", "address")


# --- D5: FI contact fields belong to the respondent --------------------------


@pytest.mark.parametrize("relationship", ["me", "child", "parent", "look_after", "not_sure"])
def test_fi_contact_fields_belong_to_respondent(relationship: str) -> None:
    answers = build(intake_type=FI, relationship=relationship)
    for field_id in CONTACT:
        field = get_field(field_id)
        assert is_about_respondent(field, answers)
        assert question_text(field, answers).startswith("What is your ")


def test_pr_contact_fields_belong_to_patient() -> None:
    answers = build(intake_type=PR)
    for field_id in CONTACT:
        field = get_field(field_id)
        assert not is_about_respondent(field, answers)
        assert "the patient's" in question_text(field, answers)


def test_patient_fields_use_other_wording_when_respondent_is_not_patient() -> None:
    answers = build(intake_type=FI, relationship="child")
    assert question_text(get_field("date_of_birth"), answers) == (
        "What is the patient's date of birth?"
    )
    me = build(intake_type=FI, relationship="me")
    assert question_text(get_field("date_of_birth"), me) == "What is your date of birth?"


@pytest.mark.parametrize(
    ("values", "applies"),
    [
        ({"intake_type": FI, "relationship": "me"}, False),
        ({"intake_type": FI, "relationship": "child"}, True),
        ({"intake_type": FI, "relationship": "not_sure"}, True),
        ({"intake_type": PR}, False),
    ],
)
def test_respondent_name_only_when_relationship_not_me(
    values: dict[str, str], applies: bool
) -> None:
    assert is_applicable(get_field("respondent_name"), build(**values)) is applies


# --- inquiry reason (P9) -----------------------------------------------------


def test_inquiry_reason_options_are_administrative() -> None:
    labels = [o.label for o in get_field("inquiry_reason").options]
    assert labels == [
        "An autism assessment",
        "Therapy or support",
        "Help at school or work",
        "Something else (type it)",
        "I'm not sure",
    ]
    assert not [label for label in labels if CONDITION_CLAIMS.search(label)]


# --- start screen count --------------------------------------------------------


def _all_paths() -> list[dict[str, str]]:
    relationships = [o.id for o in get_field("relationship").options]
    methods = [o.id for o in get_field("preferred_contact_method").options]
    fi = [
        {"intake_type": FI, "relationship": r, "preferred_contact_method": m}
        for r in relationships
        for m in methods
    ]
    return [*fi, {"intake_type": PR}]


@pytest.mark.parametrize("values", _all_paths())
def test_start_screen_count_matches_registry(values: dict[str, str]) -> None:
    assert abs(path_total(build(**values)) - ABOUT_TOTAL) <= 1


# --- Q1 update: tiers, review, submit ----------------------------------------

FI_CHILD_MUST_HAVES = {
    "intake_type": FI,
    "relationship": "child",
    "respondent_name": "Jordan Rivera",
    "full_name": "Alex Rivera",
    "preferred_contact_method": "email",
    "email": "jordan@example.com",
}


@pytest.mark.parametrize(
    ("field_id", "extra"),
    [
        ("gender", {}),
        ("preferred_name", {}),
        ("phone", {}),  # optional here: the preferred method is email
        ("referral_mode", {"intake_type": PR, "phone": "+12025550100"}),
    ],
)
def test_optional_not_sure_is_final_and_not_listed_on_review(
    field_id: str, extra: dict[str, str]
) -> None:
    base = {**FI_CHILD_MUST_HAVES, **extra}
    field = get_field(field_id)
    assert not_sure_outcome(field, build(**base)) == "final"
    answers = build(**base, **{field_id: DK})
    listed = {item.field_id for item in review_items(answers)}
    assert field_id not in listed
    for _ in range(len(FIELDS)):  # walk the rest: the field is never asked again
        nxt = next_field(answers)
        if nxt is None:
            break
        assert nxt.id != field_id
        answers = {**answers, **build(**{nxt.id: D if is_needed(nxt, answers) else SKIP})}
    assert next_field(answers) is None


def test_required_field_can_be_marked_unknown_and_submit_allowed() -> None:
    answers = build(**FI_CHILD_MUST_HAVES, date_of_birth=D, inquiry_reason="therapy_support")
    dob = get_field("date_of_birth")
    items = {i.field_id: i for i in review_items(answers)}
    assert items["date_of_birth"].state == "still_needed"
    assert items["date_of_birth"].actions == ("answer_now", "mark_unknown")
    assert can_mark_unknown(dob, answers)

    marked = {**answers, **build(date_of_birth=UNKNOWN)}
    items = {i.field_id: i for i in review_items(marked)}
    assert items["date_of_birth"].state == "not_known"
    assert items["date_of_birth"].actions == ("answer_now",)
    assert can_submit(marked)


def test_must_have_field_blocks_submit() -> None:
    answers = build(**{**FI_CHILD_MUST_HAVES, "full_name": D})
    assert not can_submit(answers)
    assert missing_must_have(answers) == ["full_name"]
    item = next(i for i in review_items(answers) if i.field_id == "full_name")
    assert item.actions == ("answer_now",)
    assert not can_mark_unknown(get_field("full_name"), answers)


def test_required_contact_field_blocks_submit() -> None:
    answers = build(**{**FI_CHILD_MUST_HAVES, "email": D})
    assert missing_must_have(answers) == ["email"]


def test_referral_needs_phone_or_email_to_submit() -> None:
    base = {"intake_type": PR, "full_name": "Alex Rivera"}
    neither = build(**base, phone=D, email=D)
    assert missing_must_have(neither) == ["phone", "email"]
    assert can_submit(build(**base, phone=D, email="alex@example.com"))


def test_required_tier_not_sure_answers_do_not_block() -> None:
    answers = build(**FI_CHILD_MUST_HAVES, inquiry_reason="not_sure", date_of_birth=UNKNOWN)
    assert not_sure_outcome(get_field("inquiry_reason"), answers) == "answer"
    assert can_submit(answers)


def test_intake_type_not_sure_is_a_clarification() -> None:
    # Domain half of test_intake_type_not_sure_is_clarification_not_repeat (Phase 4).
    assert not_sure_outcome(get_field("intake_type"), {}) == "clarify"


# --- audit #2 / #9 -------------------------------------------------------------


def test_every_question_template_has_exactly_one_question_mark() -> None:
    for field in FIELDS:
        for question in (field.question_self, field.question_other):
            assert question.count("?") == 1, question


@pytest.mark.parametrize("raw", ["May 4th 2004", "4 May 2004", "2004-05-04", "05/13/2004"])
def test_date_formats_accepted(raw: str) -> None:
    assert isinstance(
        parse_answer(get_field("date_of_birth"), raw, today=TODAY, region=REGION), Parsed
    )


def test_ambiguous_date_requires_choice() -> None:
    result = parse_answer(get_field("date_of_birth"), "04/05/2004", today=TODAY, region=REGION)
    assert isinstance(result, DateChoice)
    assert {c.display for c in result.choices} == {"April 5, 2004", "May 4, 2004"}


def test_phone_formats_normalized() -> None:
    raws = ["202-555-0100", "(202) 555-0100", "202.555.0100", "2025550100"]
    assert {normalize_phone(r, REGION) for r in raws} == {"+12025550100"}


def test_gender_options_inclusive() -> None:
    options = {o.id: o for o in get_field("gender").options}
    assert {"woman", "man", "non_binary", "another", "prefer_not", "not_sure"} <= set(options)
    assert options["another"].free_text
    assert get_field("gender").tier.value == "optional"


def test_retry_text_never_blames_user() -> None:
    blame = ("invalid", "wrong", "error", "mistake", "incorrect", "you entered", "failed")
    for text in t.RETRY.values():
        assert not any(word in text.lower() for word in blame), text


def test_preferred_name_never_in_question_text() -> None:
    for field in FIELDS:
        for question in (field.question_self, field.question_other):
            assert "{" not in question
            assert "Alex" not in question


def test_future_date_is_never_accepted() -> None:
    result = parse_answer(
        get_field("date_of_birth"), "2030-01-01", today=date(2026, 9, 26), region=REGION
    )
    assert not isinstance(result, Parsed)
