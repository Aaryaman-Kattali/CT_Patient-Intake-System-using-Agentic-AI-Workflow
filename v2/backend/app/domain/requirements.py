"""Deterministic rules: which fields apply, how strongly they are needed, what comes next,
what the review screen lists, and whether submit is allowed (docs/V2_SPEC.md §5.2-5.3)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.domain.fields import Answers, FieldDef, answer_value
from app.domain.registry import FIELDS
from app.domain.types import ANSWERED, FieldStatus, IntakeType, NotSure, Tier
from app.domain.wording import intake_type_of

ABOUT_TOTAL = 12  # "about 12 questions" on the start screen, before the path is known

CONTACT_BY_METHOD = {
    "phone_call": "phone",
    "text_message": "phone",
    "email": "email",
    "letter": "address",
}


NotSureOutcome = Literal["clarify", "answer", "defer", "final"]
_NOT_SURE_OUTCOME: dict[NotSure, NotSureOutcome] = {
    NotSure.CLARIFY: "clarify",
    NotSure.ANSWER: "answer",
    NotSure.DEFER: "defer",
}
ReviewAction = Literal["answer_now", "mark_unknown"]


def is_applicable(field: FieldDef, answers: Answers) -> bool:
    return all(c.holds(answers) for c in field.conditions)


def applicable_fields(answers: Answers) -> list[FieldDef]:
    return [f for f in sorted(FIELDS, key=lambda f: f.order) if is_applicable(f, answers)]


def _status(answers: Answers, field_id: str) -> FieldStatus | None:
    state = answers.get(field_id)
    return state.status if state is not None else None


def contact_must_have(answers: Answers) -> frozenset[str]:
    """Contact fields that are must_have right now (§5.3 note ¹)."""
    intake_type = intake_type_of(answers)
    if intake_type is None:
        return frozenset()
    if intake_type is IntakeType.FAMILY_INQUIRY:
        method = answer_value(answers, "preferred_contact_method")
        if method in CONTACT_BY_METHOD:
            return frozenset({CONTACT_BY_METHOD[method]})
    return _phone_or_email_group(answers)


def _phone_or_email_group(answers: Answers) -> frozenset[str]:
    if answer_value(answers, "phone") or answer_value(answers, "email"):
        return frozenset()
    if _status(answers, "phone") is FieldStatus.DEFERRED:
        return frozenset({"phone", "email"})
    return frozenset({"phone"})


def effective_tier(field: FieldDef, answers: Answers) -> Tier:
    if field.tier is not Tier.CONDITIONAL:
        return field.tier
    return Tier.MUST_HAVE if field.id in contact_must_have(answers) else Tier.OPTIONAL


def is_needed(field: FieldDef, answers: Answers) -> bool:
    return effective_tier(field, answers) in (Tier.MUST_HAVE, Tier.REQUIRED)


def is_resolved(field: FieldDef, answers: Answers) -> bool:
    """A field with any saved status is never asked again automatically (no repeats).

    Tiers can change after an answer (e.g. an optional email marked dont_know becomes
    must_have when the preferred method changes). The review screen lists it instead.
    """
    return _status(answers, field.id) is not None


def next_field(answers: Answers) -> FieldDef | None:
    """First unresolved needed field by order, then first unresolved optional field."""
    fields = applicable_fields(answers)
    for wanted_needed in (True, False):
        for field in fields:
            if is_needed(field, answers) == wanted_needed and not is_resolved(field, answers):
                return field
    return None


def not_sure_outcome(field: FieldDef, answers: Answers) -> NotSureOutcome:
    """What "I'm not sure" / "I don't know" does for this field right now."""
    if not is_needed(field, answers):
        return "final"
    return _NOT_SURE_OUTCOME[field.not_sure]


def can_mark_unknown(field: FieldDef, answers: Answers) -> bool:
    return (
        is_applicable(field, answers)
        and effective_tier(field, answers) is Tier.REQUIRED
        and _status(answers, field.id) not in ANSWERED
    )


class ReviewItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    field_id: str
    tier: Tier
    state: Literal["still_needed", "not_known"]
    actions: tuple[ReviewAction, ...]


def review_items(answers: Answers) -> list[ReviewItem]:
    """Missing fields for the review screen. Optional fields are never listed."""
    items: list[ReviewItem] = []
    for field in applicable_fields(answers):
        tier = effective_tier(field, answers)
        status = _status(answers, field.id)
        if tier is Tier.OPTIONAL or status in ANSWERED:
            continue
        if status is FieldStatus.UNKNOWN_CONFIRMED:
            items.append(
                ReviewItem(field_id=field.id, tier=tier, state="not_known", actions=("answer_now",))
            )
            continue
        actions: tuple[ReviewAction, ...] = (
            ("answer_now", "mark_unknown") if tier is Tier.REQUIRED else ("answer_now",)
        )
        items.append(
            ReviewItem(field_id=field.id, tier=tier, state="still_needed", actions=actions)
        )
    return items


def missing_must_have(answers: Answers) -> list[str]:
    return [
        f.id
        for f in applicable_fields(answers)
        if effective_tier(f, answers) is Tier.MUST_HAVE and _status(answers, f.id) not in ANSWERED
    ]


def can_submit(answers: Answers) -> bool:
    return not missing_must_have(answers)


def path_total(answers: Answers) -> int:
    """Number of questions on the current path (for "Question 4 of 12")."""
    return len(applicable_fields(answers))


def resolved_count(answers: Answers) -> int:
    return sum(is_resolved(f, answers) for f in applicable_fields(answers))
