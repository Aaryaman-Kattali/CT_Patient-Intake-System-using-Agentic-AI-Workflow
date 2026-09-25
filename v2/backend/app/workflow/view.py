"""What the user sees on a turn. `question` is one object or None, never a list (P1)."""

from pydantic import BaseModel, ConfigDict

from app.domain import templates as t
from app.domain.registry import get_field
from app.domain.requirements import (
    ABOUT_TOTAL,
    applicable_fields,
    can_submit,
    is_needed,
    is_resolved,
    path_total,
    resolved_count,
    review_items,
)
from app.domain.types import InputType
from app.domain.wording import question_text, section_name
from app.workflow.engine import FieldQuestion, Notes, QueueQuestion, current_question
from app.workflow.snapshot import PendingKind, Snapshot
from app.workflow.states import COLLECTING_STATES, State


class _View(BaseModel):
    model_config = ConfigDict(frozen=True)


class OptionView(_View):
    id: str
    label: str
    free_text: bool = False


class QuestionView(_View):
    kind: str  # field | confirm_extra | confirm_value | conflict | date_choice
    field_id: str
    text: str
    example: str | None
    input_type: InputType
    options: tuple[OptionView, ...]
    why: str
    can_skip: bool
    can_defer: bool


class ActionView(_View):
    id: str
    label: str


class SectionView(_View):
    name: str
    done: bool


class ProgressView(_View):
    answered: int
    about_total: int
    exact: bool
    sections: tuple[SectionView, ...]


class ReviewRow(_View):
    field_id: str
    label: str
    display: str


class ReviewMissing(_View):
    field_id: str
    label: str
    state: str
    reason: str | None
    actions: tuple[ActionView, ...]


class ReviewView(_View):
    answered: tuple[ReviewRow, ...]
    missing: tuple[ReviewMissing, ...]
    can_submit: bool


class TurnView(_View):
    state: State
    turn: int
    acknowledgement: str | None
    info: tuple[str, ...]
    question: QuestionView | None
    actions: tuple[ActionView, ...]
    progress: ProgressView
    review: ReviewView | None
    resume_code: str | None = None  # shown while paused, with a copy button


def _action(action_id: str) -> ActionView:
    return ActionView(id=action_id, label=t.BUTTONS[action_id])


def _question(snap: Snapshot) -> QuestionView | None:
    q = current_question(snap)
    if q is None:
        return None
    if isinstance(q, FieldQuestion):
        fld = q.field
        needed = is_needed(fld, snap.answers)
        return QuestionView(
            kind="field",
            field_id=fld.id,
            text=question_text(fld, snap.answers),
            example=fld.example,
            input_type=fld.input_type,
            options=tuple(
                OptionView(id=o.id, label=o.label, free_text=o.free_text) for o in fld.options
            ),
            why=fld.why,
            can_skip=not needed,
            can_defer=needed and fld.id != "intake_type",
        )
    return _queue_question(snap, q)


def _queue_question(snap: Snapshot, q: QueueQuestion) -> QuestionView:
    item, fld = q.item, get_field(q.item.field_id)
    options: tuple[OptionView, ...]
    if item.kind is PendingKind.CONFLICT:
        text = " ".join(
            [
                t.CONFLICT_EARLIER.format(old=item.old_display),
                t.CONFLICT_NOW.format(new=item.display),
                t.CONFLICT_QUESTION,
            ]
        )
        options = (
            OptionView(id="old", label=item.old_display or ""),
            OptionView(id="new", label=item.display or ""),
            OptionView(id="neither", label=t.BUTTONS["neither"]),
            OptionView(id="not_sure", label=t.BUTTONS["not_sure"]),
        )
    elif item.kind is PendingKind.DATE_CHOICE:
        text = t.DATE_CHOICE
        options = tuple(OptionView(id=ch.value, label=ch.display) for ch in item.choices)
    else:
        label = fld.short_label[:1].upper() + fld.short_label[1:]
        text = t.CONFIRM_VALUE.format(label=label, value=item.display)
        options = (
            OptionView(id="yes", label=t.BUTTONS["yes"]),
            OptionView(id="no", label=t.BUTTONS["no"]),
        )
    return QuestionView(
        kind=item.kind.value,
        field_id=fld.id,
        text=text,
        example=None,
        input_type=InputType.CHOICE,
        options=options,
        why=fld.why,
        can_skip=False,
        can_defer=False,
    )


def _progress(snap: Snapshot) -> ProgressView:
    known = snap.answers.get("intake_type") is not None
    fields = applicable_fields(snap.answers)
    sections: dict[str, bool] = {}
    for fld in fields:
        done = sections.get(fld.section, True) and is_resolved(fld, snap.answers)
        sections[fld.section] = done
    return ProgressView(
        answered=resolved_count(snap.answers),
        about_total=path_total(snap.answers) if known else ABOUT_TOTAL,
        exact=known,
        sections=tuple(
            SectionView(name=section_name(name, snap.answers), done=done)
            for name, done in sections.items()
        ),
    )


def _review(snap: Snapshot) -> ReviewView:
    answered = tuple(
        ReviewRow(field_id=f.id, label=f.short_label, display=state.display or state.value or "")
        for f in applicable_fields(snap.answers)
        if (state := snap.answers.get(f.id)) is not None and state.answered
    )
    missing = tuple(
        ReviewMissing(
            field_id=item.field_id,
            label=get_field(item.field_id).short_label,
            state=t.REVIEW_NOT_KNOWN if item.state == "not_known" else t.REVIEW_STILL_NEEDED,
            reason=item.reason,
            actions=tuple(_action(a) for a in item.actions),
        )
        for item in review_items(snap.answers)
    )
    return ReviewView(answered=answered, missing=missing, can_submit=can_submit(snap.answers))


def _actions(snap: Snapshot, notes: Notes) -> tuple[ActionView, ...]:
    ids = list(notes.actions)
    if snap.state is State.GREETING:
        ids = ["start"]
    elif snap.state is State.PAUSED:
        ids = ["resume"]
    elif snap.state is State.NEEDS_HUMAN:
        ids = ["continue_alone"]
    elif snap.state is State.REVIEW:
        ids.append("submit")
    if snap.state in COLLECTING_STATES and "take_a_break" not in ids:
        ids.append("take_a_break")
    return tuple(_action(i) for i in dict.fromkeys(ids))


def render(snap: Snapshot, notes: Notes | None = None, resume_code: str | None = None) -> TurnView:
    notes = notes or Notes()
    info = list(notes.info)
    if snap.state is State.GREETING and not info:
        info = [line.format(total=ABOUT_TOTAL) for line in t.START]
    return TurnView(
        state=snap.state,
        turn=snap.turn,
        acknowledgement=notes.acknowledgement,
        info=tuple(info),
        question=_question(snap),
        actions=_actions(snap, notes),
        progress=_progress(snap),
        review=_review(snap) if snap.state is State.REVIEW else None,
        resume_code=resume_code if snap.state is State.PAUSED else None,
    )
