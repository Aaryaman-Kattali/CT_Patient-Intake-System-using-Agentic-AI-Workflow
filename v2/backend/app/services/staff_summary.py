"""The intake summary for staff (docs/V2_SPEC.md §11.1). Deterministic; replaces V1's SOAP note.

Built only from this intake's stored fields and events, which the caller passes in. Every
statement cites its source ("field:<id>" or "event:<seq>"). The text the system writes itself
(labels and fixed phrases) is checked against the clinical deny-list. The user's own answers
are quoted as theirs, with their source cited, and are not rewritten.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.domain.clinical import CLINICAL_TERMS
from app.domain.fields import FieldDef, FieldState
from app.domain.registry import SECTION_NAMES
from app.domain.requirements import applicable_fields
from app.domain.types import FieldStatus
from app.workflow.snapshot import EventRecord, Snapshot

TITLE: Literal["Intake summary for staff"] = "Intake summary for staff"
DISCLAIMER = "Draft for staff review. Built from the form answers only. Not a clinical document."

# Fixed phrases the system writes. {label} is a field label, {value}/{other} the user's words.
ANSWER = "{label}: {value}"
TWO_ANSWERS = "{label}: Two answers given: {value} and {other}, please check."
NOT_ANSWERED = "{label}: Not answered, please follow up."
NOT_KNOWN = "{label}: Not known, please follow up."
ASKED_FOR_PERSON = "Asked to talk to a person."
CRISIS_SHOWN = "Crisis support information was shown. A staff member was asked to make contact."
TEMPLATES = (ANSWER, TWO_ANSWERS, NOT_ANSWERED, NOT_KNOWN, ASKED_FOR_PERSON, CRISIS_SHOWN)

# Staff-facing labels where the user-facing short label would read wrongly.
STAFF_LABELS = {"respondent_name": "Filled in by", "relationship": "Form is for"}


class Statement(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str
    sources: tuple[str, ...]


class StaffSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    title: Literal["Intake summary for staff"] = TITLE
    disclaimer: str = DISCLAIMER
    sections: dict[str, tuple[Statement, ...]]
    not_answered: tuple[Statement, ...]
    notes: tuple[Statement, ...]

    def statements(self) -> list[Statement]:
        return [s for part in self.sections.values() for s in part] + [
            *self.not_answered,
            *self.notes,
        ]


class SummaryInvalid(ValueError):
    pass


def staff_label(fld: FieldDef) -> str:
    label = STAFF_LABELS.get(fld.id, fld.short_label)
    return label[:1].upper() + label[1:]


def build_staff_summary(snap: Snapshot, events: list[tuple[int, EventRecord]]) -> StaffSummary:
    sections: dict[str, list[Statement]] = {}
    not_answered: list[Statement] = []
    for fld in applicable_fields(snap.answers):
        state = snap.answers.get(fld.id)
        if state is None:
            continue
        if state.answered:
            name = SECTION_NAMES[fld.section][1]
            sections.setdefault(name, []).append(_answer(fld, state, events))
        elif state.status is FieldStatus.DEFERRED:
            not_answered.append(_fixed(NOT_ANSWERED, fld))
        elif state.status in (FieldStatus.UNKNOWN_CONFIRMED, FieldStatus.DONT_KNOW):
            not_answered.append(_fixed(NOT_KNOWN, fld))
    summary = StaffSummary(
        sections={k: tuple(v) for k, v in sections.items()},
        not_answered=tuple(not_answered),
        notes=tuple(_notes(events)),
    )
    validate(summary, snap, events)
    return summary


def _answer(fld: FieldDef, state: FieldState, events: list[tuple[int, EventRecord]]) -> Statement:
    value = state.display or state.value or ""
    source = f"field:{fld.id}"
    if state.unresolved_other:
        conflict = _last_event(events, "conflict_unresolved", fld.id)
        sources = (source, f"event:{conflict}") if conflict else (source,)
        text = TWO_ANSWERS.format(label=staff_label(fld), value=value, other=state.unresolved_other)
        return Statement(text=text, sources=sources)
    return Statement(text=ANSWER.format(label=staff_label(fld), value=value), sources=(source,))


def _fixed(template: str, fld: FieldDef) -> Statement:
    return Statement(text=template.format(label=staff_label(fld)), sources=(f"field:{fld.id}",))


def _notes(events: list[tuple[int, EventRecord]]) -> list[Statement]:
    notes = []
    for seq, event in events:
        if event.type == "needs_human":
            crisis = event.payload.get("reason") == "crisis"
            text = CRISIS_SHOWN if crisis else ASKED_FOR_PERSON
            notes.append(Statement(text=text, sources=(f"event:{seq}",)))
    return notes


def _last_event(events: list[tuple[int, EventRecord]], type_: str, field_id: str) -> int | None:
    found = [seq for seq, e in events if e.type == type_ and e.field_id == field_id]
    return found[-1] if found else None


def validate(summary: StaffSummary, snap: Snapshot, events: list[tuple[int, EventRecord]]) -> None:
    """Every statement cites at least one source, and every source exists for THIS intake."""
    known = {f"field:{k}" for k in snap.answers} | {f"event:{seq}" for seq, _ in events}
    for statement in summary.statements():
        if not statement.sources:
            raise SummaryInvalid("statement without a source")
        if not set(statement.sources) <= known:
            raise SummaryInvalid("statement cites a source outside this intake")


def system_text_is_clean(text: str) -> bool:
    """For the fixed phrases and labels the system writes (tested for all of them)."""
    return CLINICAL_TERMS.search(text) is None
