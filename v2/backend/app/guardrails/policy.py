"""The policy engine: one function, consulted before every value change and side effect
(docs/V2_SPEC.md §10.3). Agents propose; this decides allow / deny / require_confirmation.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from app.domain.fields import Answers, answer_value
from app.domain.registry import BY_ID
from app.domain.requirements import can_submit, is_applicable
from app.domain.types import Source
from app.workflow.states import State


class Verdict(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_CONFIRMATION = "require_confirmation"


@dataclass(frozen=True)
class Decision:
    verdict: Verdict
    reason: str

    @property
    def allowed(self) -> bool:
        return self.verdict is Verdict.ALLOW


@dataclass(frozen=True)
class AcceptValue:
    """Save a value for a field that has no answer yet."""

    field_id: str
    source: Source
    is_extra: bool  # not the question that was asked


@dataclass(frozen=True)
class ChangeValue:
    """Replace an existing answer (correction)."""

    field_id: str
    source: Source
    quoted_correction: bool  # kind == CORRECTION and the value was quoted


@dataclass(frozen=True)
class Submit:
    pass


@dataclass(frozen=True)
class SideEffect:
    kind: Literal["send_email", "staff_summary", "benefit_demo"]


Action = AcceptValue | ChangeValue | Submit | SideEffect


def _allow(reason: str) -> Decision:
    return Decision(Verdict.ALLOW, reason)


def _deny(reason: str) -> Decision:
    return Decision(Verdict.DENY, reason)


def _confirm(reason: str) -> Decision:
    return Decision(Verdict.REQUIRE_CONFIRMATION, reason)


def decide(state: State, answers: Answers, action: Action) -> Decision:
    match action:
        case AcceptValue(field_id=field_id, source=source, is_extra=is_extra):
            return _accept(state, answers, field_id, source, is_extra)
        case ChangeValue(field_id=field_id, source=source, quoted_correction=quoted):
            return _change(state, answers, field_id, source, quoted)
        case Submit():
            if state is not State.REVIEW:
                return _deny("submit_only_from_review")
            if not can_submit(answers):
                return _deny("must_have_fields_missing")
            return _allow("ready")
        case SideEffect(kind=kind):
            return _side_effect(state, answers, kind)


def _accept(
    state: State, answers: Answers, field_id: str, source: Source, is_extra: bool
) -> Decision:
    fld = BY_ID.get(field_id)
    if state is State.SUBMITTED or fld is None or not is_applicable(fld, answers):
        return _deny("field_not_writable")
    if source is Source.INFERRED:
        return _confirm("inferred_values_need_confirmation")
    if is_extra:
        return _confirm("extra_values_need_confirmation")  # P5: never silently accepted
    return _allow("explicit_answer")


def _change(
    state: State, answers: Answers, field_id: str, source: Source, quoted: bool
) -> Decision:
    fld = BY_ID.get(field_id)
    if state is State.SUBMITTED or fld is None or not is_applicable(fld, answers):
        return _deny("field_not_writable")
    if quoted and source is Source.EXPLICIT:
        return _allow("quoted_correction")  # Q7: saved directly, with Undo
    return _confirm("change_needs_conflict_question")


def _side_effect(state: State, answers: Answers, kind: str) -> Decision:
    if state is not State.SUBMITTED:
        return _deny("side_effects_only_after_submit")
    if kind == "send_email" and not answer_value(answers, "email"):
        return _deny("no_stored_email")  # no fallback to any other record
    return _allow("submitted")
