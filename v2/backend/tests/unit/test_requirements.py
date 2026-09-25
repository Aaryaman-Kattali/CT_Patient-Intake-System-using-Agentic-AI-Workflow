from hypothesis import given
from hypothesis import strategies as st

from app.domain.registry import FIELDS, get_field
from app.domain.requirements import (
    applicable_fields,
    contact_must_have,
    effective_tier,
    next_field,
    path_total,
    resolved_count,
)
from app.domain.types import FieldStatus, IntakeType, Tier
from tests.domain_helpers import Script, build, walk

FI, PR = IntakeType.FAMILY_INQUIRY.value, IntakeType.PROVIDER_REFERRAL.value
D = FieldStatus.DEFERRED

FI_SELF: Script = {
    "intake_type": FI,
    "relationship": "me",
    "full_name": "Alex Rivera",
    "date_of_birth": "2004-05-04",
    "preferred_contact_method": "email",
    "email": "alex@example.com",
    "inquiry_reason": "autism_assessment",
}
FI_CHILD: Script = {**FI_SELF, "relationship": "child", "respondent_name": "Jordan Rivera"}
PR_BASIC: Script = {
    "intake_type": PR,
    "full_name": "Alex Rivera",
    "date_of_birth": "2004-05-04",
    "phone": "+12025550100",
    "referral_provider_name": "Dr. Sam Lee",
    "referral_type": "specialist",
    "referral_date": "2026-09-01",
}


def test_first_question_is_intake_type() -> None:
    field = next_field({})
    assert field is not None
    assert field.id == "intake_type"


def test_family_inquiry_self_path_order() -> None:
    asked, _ = walk(FI_SELF)
    assert asked == [
        "intake_type",
        "relationship",
        "full_name",
        "date_of_birth",
        "preferred_contact_method",
        "email",  # must_have because preferred method is email
        "inquiry_reason",
        "phone",  # optional fields come after all needed ones
        "address",
        "preferred_name",
        "gender",
    ]


def test_family_inquiry_for_child_asks_respondent_name_after_relationship() -> None:
    asked, _ = walk(FI_CHILD)
    assert asked[:4] == ["intake_type", "relationship", "respondent_name", "full_name"]


def test_provider_referral_path_order() -> None:
    asked, _ = walk(PR_BASIC)
    assert asked == [
        "intake_type",
        "full_name",
        "date_of_birth",
        "phone",
        "referral_provider_name",
        "referral_type",
        "referral_date",
        "email",
        "address",
        "referral_mode",
        "preferred_name",
        "gender",
    ]


def test_path_total_matches_questions_asked() -> None:
    for script in (FI_SELF, FI_CHILD, PR_BASIC):
        asked, answers = walk(script)
        assert path_total(answers) == len(asked)
        assert resolved_count(answers) == len(asked)


# --- contact rule (§5.3 note 1) ---------------------------------------------


def test_fi_preferred_method_selects_the_must_have_contact() -> None:
    cases = {"phone_call": "phone", "text_message": "phone", "email": "email", "letter": "address"}
    for method, field_id in cases.items():
        answers = build(intake_type=FI, relationship="me", preferred_contact_method=method)
        assert contact_must_have(answers) == {field_id}


def test_fi_not_sure_method_falls_back_to_phone_or_email_group() -> None:
    answers = build(intake_type=FI, relationship="me", preferred_contact_method="not_sure")
    assert contact_must_have(answers) == {"phone"}


def test_fi_deferred_method_falls_back_to_phone_or_email_group() -> None:
    answers = build(intake_type=FI, relationship="me", preferred_contact_method=D)
    assert contact_must_have(answers) == {"phone"}


def test_deferred_phone_makes_email_must_have() -> None:
    answers = build(intake_type=PR, phone=D)
    assert contact_must_have(answers) == {"phone", "email"}
    assert effective_tier(get_field("email"), answers) is Tier.MUST_HAVE
    field = next_field({**answers, **build(full_name="A B", date_of_birth=D)})
    assert field is not None
    assert field.id == "email"


def test_answered_email_satisfies_the_group() -> None:
    answers = build(intake_type=PR, phone=D, email="alex@example.com")
    assert contact_must_have(answers) == frozenset()
    assert effective_tier(get_field("phone"), answers) is Tier.OPTIONAL


def test_no_contact_field_is_needed_before_intake_type() -> None:
    assert contact_must_have({}) == frozenset()


def test_family_only_fields_hidden_for_referrals() -> None:
    ids = {f.id for f in applicable_fields(build(intake_type=PR))}
    assert not ids & {"relationship", "respondent_name", "preferred_contact_method"}
    assert not ids & {"inquiry_reason"}


# --- property: no field is ever asked twice ----------------------------------

_value_or_status = st.one_of(
    st.none(), st.sampled_from([D, FieldStatus.DONT_KNOW, FieldStatus.SKIPPED])
)


@given(
    intake_type=st.sampled_from([FI, PR]),
    relationship=st.sampled_from(["me", "child", "not_sure", None]),
    method=st.sampled_from(["phone_call", "email", "letter", "not_sure", None]),
    others=st.fixed_dictionaries({f.id: _value_or_status for f in FIELDS}),
)
def test_next_field_never_repeats_a_resolved_field(
    intake_type: str,
    relationship: str | None,
    method: str | None,
    others: dict[str, FieldStatus | None],
) -> None:
    script: Script = {k: v for k, v in others.items() if v is not None}
    script["intake_type"] = intake_type
    for field_id, value in (("relationship", relationship), ("preferred_contact_method", method)):
        if value is not None:
            script[field_id] = value
    asked, _ = walk(script)
    assert len(asked) == len(set(asked))


def test_tier_change_never_causes_a_repeat_and_shows_on_review() -> None:
    # Found by the property test: email was optional and marked dont_know, then the
    # preferred method changed to Email, making it must_have. It must not be re-asked.
    from app.domain.requirements import can_submit, review_items

    answers = build(
        intake_type=FI,
        relationship="me",
        full_name="Alex Rivera",
        preferred_contact_method="email",
        email=FieldStatus.DONT_KNOW,
    )
    field = next_field(answers)
    assert field is None or field.id != "email"
    assert "email" in {item.field_id for item in review_items(answers)}
    assert not can_submit(answers)
