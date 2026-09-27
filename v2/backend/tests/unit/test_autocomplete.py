"""Autofill hints only for information about the person typing (WCAG 1.3.5)."""

import pytest

from app.domain.fields import FieldState
from app.domain.registry import FIELDS, get_field
from app.domain.types import FieldStatus
from app.domain.wording import autocomplete_hint


def _answers(intake_type: str, relationship: str | None = None) -> dict[str, FieldState]:
    answers = {"intake_type": FieldState(status=FieldStatus.ACCEPTED, value=intake_type)}
    if relationship:
        answers["relationship"] = FieldState(status=FieldStatus.ACCEPTED, value=relationship)
    return answers


def _hint(field_id: str, intake_type: str, relationship: str | None = None) -> str:
    return autocomplete_hint(get_field(field_id), _answers(intake_type, relationship))


FI, PR = "family_inquiry", "provider_referral"


@pytest.mark.parametrize(
    ("field_id", "relationship", "hint"),
    [
        ("full_name", "me", "name"),
        ("date_of_birth", "me", "bday"),
        ("phone", "me", "tel"),
        ("email", "me", "email"),
        ("address", "me", "street-address"),
        # Filling in for someone else: the patient's name and birthday are never autofilled.
        ("full_name", "child", "off"),
        ("date_of_birth", "child", "off"),
        ("full_name", "parent", "off"),
        # The respondent's own name and contact details (they are about the person typing).
        ("respondent_name", "child", "name"),
        ("phone", "child", "tel"),
        ("email", "child", "email"),
        ("address", "child", "street-address"),
        ("preferred_name", "me", "off"),
    ],
)
def test_family_inquiry_hints(field_id: str, relationship: str, hint: str) -> None:
    assert _hint(field_id, FI, relationship) == hint


@pytest.mark.parametrize("field_id", [f.id for f in FIELDS])
def test_provider_referral_never_autofills(field_id: str) -> None:
    assert _hint(field_id, PR) == "off"  # a health worker types someone else's details


def test_unknown_relationship_is_off() -> None:
    assert _hint("full_name", FI) == "off"
    assert _hint("date_of_birth", FI) == "off"
