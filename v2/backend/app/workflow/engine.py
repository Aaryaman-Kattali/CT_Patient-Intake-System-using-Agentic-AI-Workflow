"""The deterministic workflow engine (docs/V2_SPEC.md §6.3-§7).

`handle` is pure: (snapshot, command, understanding) -> new snapshot + events + notes.
It never does I/O and never calls the LLM. It decides question order, what is saved,
and every state change. The LLM's output is only ever a proposal.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

from app.config import CrisisContent
from app.domain import templates as t
from app.domain.fields import FieldDef, FieldState, answer_value
from app.domain.normalizers import match_yes_no
from app.domain.parsing import (
    Confirm,
    DateChoice,
    Parsed,
    ParseResult,
    Retry,
    match_option,
    parse_answer,
    parse_choice,
)
from app.domain.registry import BY_ID, get_field
from app.domain.requirements import (
    can_mark_unknown,
    can_submit,
    is_applicable,
    is_needed,
    missing_must_have,
    next_field,
    not_sure_outcome,
)
from app.domain.types import FieldStatus, InputType, Source
from app.workflow import commands as c
from app.workflow.snapshot import (
    Choice,
    EventRecord,
    PendingItem,
    PendingKind,
    Snapshot,
    UndoRecord,
)
from app.workflow.states import COLLECTING_STATES, State
from app.workflow.transitions import Trigger, allowed, check
from app.workflow.understanding import FieldProposal, ReplyKind, ReplyUnderstanding


@dataclass(frozen=True)
class EngineConfig:
    today: date
    region: str
    max_field_attempts: int
    crisis: CrisisContent


@dataclass
class Notes:
    """Transient text for this turn only. Never persisted; never contains a question."""

    acknowledgement: str | None = None
    info: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Applied:
    snapshot: Snapshot
    events: tuple[EventRecord, ...]
    notes: Notes


@dataclass(frozen=True)
class Rejected:
    reason: str
    notes: Notes


Result = Applied | Rejected


@dataclass(frozen=True)
class FieldQuestion:
    field: FieldDef
    pinned: bool


@dataclass(frozen=True)
class QueueQuestion:
    item: PendingItem


CurrentQuestion = FieldQuestion | QueueQuestion


def current_question(snap: Snapshot) -> CurrentQuestion | None:
    """The single question to show now, or None. Exactly one source of truth."""
    if snap.state not in COLLECTING_STATES or snap.state is State.REVIEW or snap.interruption:
        return None
    if snap.queue:
        return QueueQuestion(snap.queue[0])
    if snap.pinned_field:
        return FieldQuestion(get_field(snap.pinned_field), pinned=True)
    nxt = next_field(snap.answers)
    return FieldQuestion(nxt, pinned=False) if nxt else None


def derive_state(snap: Snapshot) -> State:
    """The state implied by the answers and queue, for collecting states."""
    if snap.queue:
        kind = snap.queue[0].kind
        return State.RESOLVING_CONFLICT if kind is PendingKind.CONFLICT else State.CONFIRMING_EXTRA
    if snap.pinned_field:
        return State.CHOOSE_INTAKE_TYPE if snap.pinned_field == "intake_type" else State.COLLECTING
    if answer_value(snap.answers, "intake_type") is None:
        return State.CHOOSE_INTAKE_TYPE
    if snap.return_to_review or next_field(snap.answers) is None:
        return State.REVIEW
    return State.COLLECTING


_CONFIRM_KINDS = frozenset({PendingKind.CONFIRM_EXTRA, PendingKind.CONFIRM_VALUE})


def needs_understanding(snap: Snapshot, text: str) -> bool:
    """False when typed text can be handled deterministically (yes/no, date picks)."""
    q = current_question(snap)
    confirming = isinstance(q, QueueQuestion) and q.item.kind in _CONFIRM_KINDS
    return not (confirming and match_yes_no(text) is not None)


# ---------------------------------------------------------------------------


class _Turn:
    """Mutable working copy for one command. Produces an Applied result."""

    def __init__(self, snap: Snapshot, config: EngineConfig) -> None:
        self.start = snap
        self.config = config
        self.state = snap.state
        self.resume_state = snap.resume_state
        self.answers = dict(snap.answers)
        self.queue = list(snap.queue)
        self.pinned = snap.pinned_field
        self.return_to_review = snap.return_to_review
        self.interruption = snap.interruption
        self.attempts = dict(snap.attempts)
        self.undo: UndoRecord | None = None  # undo only survives one turn
        self.resume_code_hash = snap.resume_code_hash
        self.events: list[EventRecord] = []
        self.notes = Notes()

    def event(self, type_: str, field_id: str | None = None, **payload: object) -> None:
        self.events.append(EventRecord(type=type_, field_id=field_id, payload=dict(payload)))

    def snapshot(self, state: State) -> Snapshot:
        return Snapshot(
            id=self.start.id,
            state=state,
            turn=self.start.turn + 1,
            resume_state=self.resume_state,
            answers=self.answers,
            queue=tuple(self.queue),
            pinned_field=self.pinned,
            return_to_review=self.return_to_review,
            interruption=self.interruption,
            attempts=self.attempts,
            undo=self.undo,
            resume_code_hash=self.resume_code_hash,
        )

    def view_snapshot(self) -> Snapshot:
        return self.snapshot(self.state)

    def finish(self, trigger: Trigger, target: State | None = None) -> Applied:
        if target is None:
            target = derive_state(self.view_snapshot())
            if target is State.REVIEW:
                self.return_to_review = True
        check(self.start.state, trigger, target)
        if target is not self.start.state:
            self.event("state_changed", from_=self.start.state.value, to=target.value)
        snap = self.snapshot(target)
        question = current_question(snap)
        if question is not None:
            field_id, kind, pinned = _question_facts(question)
            self.event("question_shown", field_id, kind=kind, pinned=pinned)
        return Applied(snapshot=snap, events=tuple(self.events), notes=self.notes)

    # --- saving -----------------------------------------------------------------

    def set_field(self, field_id: str, state: FieldState, event: str, **payload: object) -> None:
        self.answers[field_id] = state
        self.attempts.pop(field_id, None)
        if self.pinned == field_id:
            self.pinned = None
        self.event(event, field_id, status=state.status.value, source=_src(state), **payload)

    def accept(self, fld: FieldDef, parsed: Parsed, source: Source, status: FieldStatus) -> None:
        previous = self.answers.get(fld.id)
        edit = self.pinned == fld.id and previous is not None
        new = FieldState(
            status=status,
            value=parsed.value,
            display=parsed.display,
            extra_text=parsed.extra_text,
            source=Source.REVIEW_EDIT if edit else source,
        )
        kind = "field_corrected" if edit else _accepted_event(status)
        self.set_field(fld.id, new, kind)
        self.notes.acknowledgement = t.SAVED

    def mark(self, fld: FieldDef, status: FieldStatus, event: str, ack: str) -> None:
        self.set_field(fld.id, FieldState(status=status), event)
        self.notes.acknowledgement = ack


def _src(state: FieldState) -> str | None:
    return state.source.value if state.source else None


def _accepted_event(status: FieldStatus) -> str:
    return "field_confirmed" if status is FieldStatus.CONFIRMED else "field_accepted"


def _question_facts(q: CurrentQuestion) -> tuple[str, str, bool]:
    if isinstance(q, QueueQuestion):
        return q.item.field_id, q.item.kind.value, False
    return q.field.id, "field", q.pinned


# ---------------------------------------------------------------------------


def handle(
    snap: Snapshot,
    command: c.Command,
    config: EngineConfig,
    understanding: ReplyUnderstanding | None = None,
) -> Result:
    turn = _Turn(snap, config)
    match command:
        case c.Start():
            return _guarded(turn, Trigger.START, lambda: turn.finish(Trigger.START))
        case c.Choose():
            return _choose(turn, command)
        case c.Text():
            return _text(turn, command.text, understanding)
        case c.Skip():
            return _skip(turn)
        case c.Pause():
            return _pause(turn, command)
        case c.Resume():
            return _resume(turn, Trigger.RESUME)
        case c.TalkToPerson():
            return _needs_human(turn, crisis=False)
        case c.ContinueAlone():
            return _resume(turn, Trigger.CONTINUE_ALONE)
        case c.KeepGoing():
            return _keep_going(turn)
        case c.Undo():
            return _undo(turn)
        case c.EditField():
            return _edit_field(turn, command.field_id)
        case c.MarkUnknown():
            return _mark_unknown(turn, command.field_id)
        case c.Submit():
            return _submit(turn)


def _reject(reason: str, *info: str) -> Rejected:
    return Rejected(reason=reason, notes=Notes(info=list(info)))


def _guarded(turn: _Turn, trigger: Trigger, run: Callable[[], Result]) -> Result:
    if not allowed(turn.start.state, trigger):
        return _reject("not_allowed_in_state")
    return run()


# --- buttons ---------------------------------------------------------------


def _choose(turn: _Turn, cmd: c.Choose) -> Result:
    q = current_question(turn.start)
    if q is None or not allowed(turn.start.state, Trigger.ANSWER):
        return _reject("no_question")
    if isinstance(q, QueueQuestion):
        return _resolve_queue(turn, q.item, cmd.option_id)
    fld = q.field
    if fld.input_type is not InputType.CHOICE:
        return _reject("not_a_choice_question")
    option = fld.option(cmd.option_id)
    if option is None:
        return _retry(turn, fld, "choose_option")
    if option.special == "not_sure":
        return _not_sure(turn, fld)
    result = parse_choice(fld, cmd.option_id, cmd.extra_text)
    if isinstance(result, Parsed):
        turn.accept(fld, result, Source.BUTTON, FieldStatus.ACCEPTED)
        return turn.finish(Trigger.ANSWER)
    return _retry(turn, fld, result.code if isinstance(result, Retry) else "choose_option")


def _not_sure(turn: _Turn, fld: FieldDef) -> Result:
    outcome = not_sure_outcome(fld, turn.answers)
    if outcome == "clarify":  # intake_type: explain, then the same buttons again
        turn.notes.info.append(fld.help)
        turn.event("clarification_shown", fld.id, reason="not_sure")
        return turn.finish(Trigger.INFO, turn.start.state)
    if outcome == "answer":
        option = fld.option("not_sure")
        label = option.label if option else "I'm not sure"
        turn.accept(fld, Parsed("not_sure", label), Source.BUTTON, FieldStatus.ACCEPTED)
        turn.notes.acknowledgement = t.NOT_SURE_OK
    elif outcome == "defer":
        turn.mark(fld, FieldStatus.DEFERRED, "field_deferred", t.NOT_SURE_OK)
    else:
        turn.mark(fld, FieldStatus.DONT_KNOW, "field_dont_know", t.NOT_SURE_OK)
    return turn.finish(Trigger.ANSWER)


def _resolve_queue(turn: _Turn, item: PendingItem, choice: str) -> Result:
    fld = get_field(item.field_id)
    if item.kind in (PendingKind.CONFIRM_EXTRA, PendingKind.CONFIRM_VALUE):
        if choice not in ("yes", "no"):
            return _reject("choose_yes_or_no", t.RETRY["choose_option"])
        turn.queue.pop(0)
        if choice == "yes":
            turn.accept(fld, _item_parsed(item), item.source, FieldStatus.CONFIRMED)
        else:
            turn.event("field_rejected", fld.id, kind=item.kind.value)
        return turn.finish(Trigger.ANSWER)
    if item.kind is PendingKind.DATE_CHOICE:
        picked = next((ch for ch in item.choices if ch.value == choice), None)
        if picked is None:
            return _reject("choose_a_date", t.RETRY["choose_option"])
        turn.queue.pop(0)
        turn.accept(fld, Parsed(picked.value, picked.display), item.source, FieldStatus.CONFIRMED)
        return turn.finish(Trigger.ANSWER)
    return _resolve_conflict(turn, item, fld, choice)


def _resolve_conflict(turn: _Turn, item: PendingItem, fld: FieldDef, choice: str) -> Result:
    if choice not in ("old", "new", "neither", "not_sure"):
        return _reject("choose_a_value", t.RETRY["choose_option"])
    turn.queue.pop(0)
    if choice == "not_sure":  # keep the earlier value, but flag both for staff
        current = turn.answers[fld.id]
        turn.answers[fld.id] = current.model_copy(update={"unresolved_other": item.display})
        turn.event("conflict_unresolved", fld.id, kept=current.display, other=item.display)
        turn.notes.acknowledgement = t.NOT_SURE_OK
        return turn.finish(Trigger.ANSWER)
    turn.event("conflict_resolved", fld.id, kept=choice)
    if choice == "new":
        new = FieldState(
            status=FieldStatus.CONFIRMED,
            value=item.value,
            display=item.display,
            extra_text=item.extra_text,
            source=item.source,
        )
        turn.set_field(fld.id, new, "field_corrected")
        turn.notes.acknowledgement = t.SAVED
    elif choice == "neither":  # both are wrong: ask this field again, now
        turn.answers.pop(fld.id, None)
        turn.event("field_cleared", fld.id)
        turn.pinned = fld.id
    return turn.finish(Trigger.ANSWER)


def _item_parsed(item: PendingItem) -> Parsed:
    return Parsed(item.value or "", item.display or "", extra_text=item.extra_text)


def _skip(turn: _Turn) -> Result:
    q = current_question(turn.start)
    if not isinstance(q, FieldQuestion) or not allowed(turn.start.state, Trigger.ANSWER):
        return _reject("nothing_to_skip")
    fld = q.field
    if fld.id == "intake_type":
        return _reject("cannot_skip_intake_type")
    if is_needed(fld, turn.answers):
        turn.mark(fld, FieldStatus.DEFERRED, "field_deferred", t.ANSWER_LATER)
    else:
        turn.mark(fld, FieldStatus.SKIPPED, "field_skipped", t.SKIPPED)
    return turn.finish(Trigger.ANSWER)


def _retry(turn: _Turn, fld: FieldDef, code: str) -> Result:
    turn.attempts[fld.id] = turn.attempts.get(fld.id, 0) + 1
    turn.notes.info.append(t.RETRY[code])
    if fld.example:
        turn.notes.info.append(t.RETRY_EXAMPLE.format(example=fld.example))
    turn.event("answer_not_read", fld.id, code=code, attempt=turn.attempts[fld.id])
    if turn.attempts[fld.id] >= turn.config.max_field_attempts:
        turn.notes.info.append(t.MANY_TRIES)
        turn.notes.actions += ["answer_later", "talk_to_a_person"]
    return turn.finish(Trigger.INFO, turn.start.state)


# --- typed text -----------------------------------------------------------------


def _text(turn: _Turn, text: str, u: ReplyUnderstanding | None) -> Result:
    start = turn.start
    if start.state not in COLLECTING_STATES or start.state is State.REVIEW:
        return _reject("no_question")
    q = current_question(start)
    if isinstance(q, QueueQuestion) and q.item.kind in (
        PendingKind.CONFIRM_EXTRA,
        PendingKind.CONFIRM_VALUE,
    ):
        yes_no = match_yes_no(text)
        if yes_no is not None:
            return _resolve_queue(turn, q.item, "yes" if yes_no else "no")
    if u is None:
        return _reject("understanding_required")
    match u.kind:
        case ReplyKind.PAUSE:  # the service turns this into a Pause command with a code
            return _reject("pause_needs_command")
        case ReplyKind.DISTRESS:
            if u.distress_level == "crisis":
                return _needs_human(turn, crisis=True)
            turn.interruption = "overwhelmed"
            turn.notes.info += list(t.OVERWHELMED)
            turn.notes.actions += ["take_a_break", "talk_to_a_person", "keep_going"]
            turn.event("distress_shown", level="overwhelmed")
            return turn.finish(Trigger.INFO, start.state)
        case ReplyKind.UNSAFE:
            turn.notes.info.append(t.UNSAFE)
            turn.event("unsafe_blocked")
            return turn.finish(Trigger.INFO, start.state)
        case ReplyKind.OFF_TOPIC:
            turn.notes.info.append(t.OFF_TOPIC)
            turn.event("off_topic")
            return turn.finish(Trigger.INFO, start.state)
        case ReplyKind.CLARIFICATION:
            return _clarify(turn, q, u)
        case ReplyKind.DONT_KNOW | ReplyKind.SKIP:
            return _dont_know_or_skip(turn, q, u.kind)
        case _:
            return _answer(turn, q, u)


def _clarify(turn: _Turn, q: CurrentQuestion | None, u: ReplyUnderstanding) -> Result:
    if q is None:
        return _reject("no_question")
    fld = get_field(q.item.field_id) if isinstance(q, QueueQuestion) else q.field
    turn.notes.info.append(fld.why if u.clarification == "why" else fld.help)
    turn.event("clarification_shown", fld.id, reason=u.clarification or "meaning")
    return turn.finish(Trigger.INFO, turn.start.state)


def _dont_know_or_skip(turn: _Turn, q: CurrentQuestion | None, kind: ReplyKind) -> Result:
    if isinstance(q, FieldQuestion):
        if kind is ReplyKind.SKIP:
            return _skip(turn)
        return _not_sure(turn, q.field)
    if isinstance(q, QueueQuestion):
        if q.item.kind is PendingKind.CONFLICT:  # unsure which: keep earlier, flag both
            return _resolve_queue(turn, q.item, "not_sure")
        if q.item.kind in (PendingKind.CONFIRM_EXTRA, PendingKind.CONFIRM_VALUE):
            return _resolve_queue(turn, q.item, "no")
    turn.notes.info.append(t.NOT_UNDERSTOOD)
    return turn.finish(Trigger.INFO, turn.start.state)


def _answer(turn: _Turn, q: CurrentQuestion | None, u: ReplyUnderstanding) -> Result:
    if not isinstance(q, FieldQuestion):
        turn.notes.info.append(t.NOT_UNDERSTOOD)
        turn.event("answer_not_read", reason="answer_while_confirming")
        return turn.finish(Trigger.INFO, turn.start.state)
    fld = q.field
    main = [p for p in u.proposals if p.field_id == fld.id]
    extras = [p for p in u.proposals if p.field_id != fld.id]
    changed = False
    if main:
        reading = _interpret(fld, main[0], turn.config)
        if reading is None:  # the agent's value does not match its own quote
            turn.event("proposal_rejected", fld.id, reason="value_not_in_quote")
        elif isinstance(reading[0], Retry):
            if not extras:
                return _retry(turn, fld, reading[0].code)
            turn.event("answer_not_read", fld.id, code=reading[0].code)
        else:
            _apply_main(turn, fld, *reading)
            changed = True
    for proposal in sorted(extras, key=lambda p: _order(p.field_id)):
        changed |= _apply_extra(turn, proposal, u.kind)
    if not changed:
        turn.notes.info.append(t.NOT_UNDERSTOOD)
        turn.event("answer_not_read", fld.id, reason="no_usable_proposal")
        return turn.finish(Trigger.INFO, turn.start.state)
    return turn.finish(Trigger.ANSWER)


def _order(field_id: str) -> int:
    return BY_ID[field_id].order if field_id in BY_ID else 10_000


Reading = tuple[ParseResult, Source]


def _interpret(fld: FieldDef, p: FieldProposal, config: EngineConfig) -> Reading | None:
    """Derive the value from the quoted text with our own parsers (spec §6.3 step 3).

    Returns None when the agent's value disagrees with its own quote (hallucination).
    """
    stated = Source.EXPLICIT if p.source == "explicit" else Source.INFERRED
    if fld.input_type is InputType.CHOICE:
        return _interpret_choice(fld, p, stated)
    parsed = parse_answer(fld, p.raw_text, today=config.today, region=config.region)
    if isinstance(parsed, Parsed) and not _agrees(fld, p, parsed, config):
        return None
    return parsed, stated


def _agrees(fld: FieldDef, p: FieldProposal, parsed: Parsed, config: EngineConfig) -> bool:
    """The LLM's value must match what we read from the quote (hallucination check)."""
    if fld.input_type is InputType.TEXT:
        return p.value.strip().casefold() == parsed.value.casefold()
    theirs = parse_answer(fld, p.value, today=config.today, region=config.region)
    if isinstance(theirs, Parsed):
        return theirs.value == parsed.value
    return True  # e.g. the LLM wrote an ISO date we cannot re-read: the quote decides


def _interpret_choice(fld: FieldDef, p: FieldProposal, stated: Source) -> Reading:
    exact = match_option(fld, p.raw_text)
    if exact is not None and not exact.free_text and exact.special is None:
        return Parsed(exact.id, exact.label), stated  # the user typed the option itself
    option = fld.option(p.value)
    if option is None or option.special is not None:
        return Retry("choose_option"), Source.INFERRED
    if option.free_text:  # their words, but the category is our reading
        return parse_choice(fld, option.id, p.raw_text), Source.INFERRED
    return Parsed(option.id, option.label), Source.INFERRED  # "my mum" -> parent


def _apply_main(turn: _Turn, fld: FieldDef, outcome: ParseResult, source: Source) -> None:
    if isinstance(outcome, Parsed) and source is Source.EXPLICIT:
        turn.accept(fld, outcome, source, FieldStatus.ACCEPTED)
    elif isinstance(outcome, Parsed):
        turn.queue.insert(0, _pending(PendingKind.CONFIRM_VALUE, fld, outcome, Source.INFERRED))
        turn.event("field_proposed", fld.id, source="inferred")
    elif isinstance(outcome, Confirm):
        turn.queue.insert(0, _pending(PendingKind.CONFIRM_VALUE, fld, outcome.value, source))
        turn.event("field_proposed", fld.id, source=source.value, reason="one_reading")
    elif isinstance(outcome, DateChoice):
        turn.queue.insert(0, _date_choice(fld, outcome, source))
        turn.event("field_proposed", fld.id, source=source.value, reason="ambiguous_date")


def _apply_extra(turn: _Turn, p: FieldProposal, kind: ReplyKind) -> bool:
    fld = BY_ID.get(p.field_id)
    if fld is None or not is_applicable(fld, turn.answers) or fld.id == "intake_type":
        turn.event("proposal_dropped", p.field_id if fld else None, reason="not_applicable")
        return False
    if any(item.field_id == fld.id for item in turn.queue):
        return False
    reading = _interpret(fld, p, turn.config)
    if reading is None:
        turn.event("proposal_dropped", fld.id, reason="value_not_in_quote")
        return False
    outcome, source = reading
    if isinstance(outcome, Retry):
        turn.event("proposal_dropped", fld.id, reason="unreadable")
        return False
    current = turn.answers.get(fld.id)
    if current is not None and current.answered:
        return _extra_for_answered(turn, fld, outcome, source, current, kind)
    if isinstance(outcome, DateChoice):
        turn.queue.append(_date_choice(fld, outcome, source))
    else:
        value = outcome.value if isinstance(outcome, Confirm) else outcome
        turn.queue.append(_pending(PendingKind.CONFIRM_EXTRA, fld, value, source))
    turn.event("field_proposed", fld.id, source=source.value, reason="extra")
    return True


def _extra_for_answered(
    turn: _Turn,
    fld: FieldDef,
    outcome: ParseResult,
    source: Source,
    current: FieldState,
    kind: ReplyKind,
) -> bool:
    if isinstance(outcome, DateChoice):
        turn.queue.append(_date_choice(fld, outcome, source))
        turn.event("field_proposed", fld.id, source=source.value, reason="ambiguous_date")
        return True
    parsed = outcome.value if isinstance(outcome, Confirm) else outcome
    if not isinstance(parsed, Parsed) or parsed.value == current.value:
        return False
    quoted = kind is ReplyKind.CORRECTION and source is Source.EXPLICIT
    if quoted and isinstance(outcome, Parsed):  # Q7: explicit correction, quoted -> save + Undo
        new = FieldState(
            status=FieldStatus.ACCEPTED,
            value=parsed.value,
            display=parsed.display,
            extra_text=parsed.extra_text,
            source=Source.EXPLICIT,
        )
        turn.set_field(fld.id, new, "field_corrected", previous=current.value)
        turn.undo = UndoRecord(
            field_id=fld.id, previous=current, valid_for_turn=turn.start.turn + 1
        )
        turn.notes.acknowledgement = t.UPDATED.format(
            short_label=fld.short_label, value=parsed.display
        )
        turn.notes.actions.append("undo")
        return True
    item = _pending(PendingKind.CONFLICT, fld, parsed, source)
    turn.queue.append(item.model_copy(update={"old_display": current.display or current.value}))
    turn.event("conflict_detected", fld.id, source=source.value)
    return True


def _pending(kind: PendingKind, fld: FieldDef, parsed: Parsed, source: Source) -> PendingItem:
    return PendingItem(
        kind=kind,
        field_id=fld.id,
        value=parsed.value,
        display=parsed.display,
        extra_text=parsed.extra_text,
        source=source,
    )


def _date_choice(fld: FieldDef, outcome: DateChoice, source: Source) -> PendingItem:
    return PendingItem(
        kind=PendingKind.DATE_CHOICE,
        field_id=fld.id,
        source=source,
        choices=tuple(Choice(value=ch.value, display=ch.display) for ch in outcome.choices),
    )


# --- pause, people, undo, review ---------------------------------------------


def _pause(turn: _Turn, cmd: c.Pause) -> Result:
    if not allowed(turn.start.state, Trigger.PAUSE):
        return _reject("not_allowed_in_state")
    turn.resume_state = turn.start.state
    turn.interruption = None
    turn.resume_code_hash = turn.resume_code_hash or cmd.resume_code_hash
    turn.notes.info += list(t.PAUSED)
    turn.event("paused")
    return turn.finish(Trigger.PAUSE, State.PAUSED)


def _resume(turn: _Turn, trigger: Trigger) -> Result:
    if not allowed(turn.start.state, trigger) or turn.start.resume_state is None:
        return _reject("not_allowed_in_state")
    target = turn.start.resume_state
    turn.resume_state = None
    name = answer_value(turn.answers, "preferred_name")
    turn.notes.info.append(t.WELCOME_BACK_NAME.format(name=name) if name else t.WELCOME_BACK)
    turn.event("resumed", via=trigger.value)
    return turn.finish(trigger, target)


def _needs_human(turn: _Turn, *, crisis: bool) -> Result:
    if not allowed(turn.start.state, Trigger.NEEDS_HUMAN):
        return _reject("not_allowed_in_state")
    turn.resume_state = turn.start.state
    turn.interruption = None
    if crisis:
        crisis_text = turn.config.crisis
        turn.notes.info += [crisis_text.heading, *crisis_text.lines]
        turn.event("distress_shown", level="crisis")
    turn.notes.info.append(t.NEEDS_HUMAN)
    turn.notes.actions.append("continue_alone")
    turn.event("needs_human", reason="crisis" if crisis else "requested")
    return turn.finish(Trigger.NEEDS_HUMAN, State.NEEDS_HUMAN)


def _keep_going(turn: _Turn) -> Result:
    if turn.start.interruption is None or not allowed(turn.start.state, Trigger.INFO):
        return _reject("nothing_to_continue")
    turn.interruption = None
    turn.event("distress_dismissed")
    return turn.finish(Trigger.INFO, turn.start.state)


def _undo(turn: _Turn) -> Result:
    record = turn.start.undo
    if record is None or record.valid_for_turn != turn.start.turn:
        return _reject("undo_not_available")
    if not allowed(turn.start.state, Trigger.UNDO):
        return _reject("not_allowed_in_state")
    fld = get_field(record.field_id)
    if record.previous is None:
        turn.answers.pop(fld.id, None)
    else:
        turn.answers[fld.id] = record.previous
    turn.event("correction_undone", fld.id, restored=record.previous is not None)
    display = record.previous.display or record.previous.value if record.previous else None
    turn.notes.acknowledgement = t.UNDONE.format(short_label=fld.short_label, value=display or "")
    return turn.finish(Trigger.UNDO)


def _edit_field(turn: _Turn, field_id: str) -> Result:
    fld = BY_ID.get(field_id)
    if turn.start.state is not State.REVIEW or fld is None or not is_applicable(fld, turn.answers):
        return _reject("cannot_edit")
    turn.pinned = fld.id
    turn.return_to_review = True
    turn.event("review_edit_started", fld.id)
    return turn.finish(Trigger.EDIT_FIELD)


def _mark_unknown(turn: _Turn, field_id: str) -> Result:
    fld = BY_ID.get(field_id)
    if (
        turn.start.state is not State.REVIEW
        or fld is None
        or not can_mark_unknown(fld, turn.answers)
    ):
        return _reject("cannot_mark_unknown")
    turn.set_field(fld.id, FieldState(status=FieldStatus.UNKNOWN_CONFIRMED), "field_marked_unknown")
    return turn.finish(Trigger.MARK_UNKNOWN, State.REVIEW)


def _submit(turn: _Turn) -> Result:
    if turn.start.state is not State.REVIEW:
        return _reject("not_allowed_in_state")
    if not can_submit(turn.answers):
        turn.notes.info.append(t.REVIEW_CANNOT_SUBMIT)
        turn.event("submit_blocked", missing=missing_must_have(turn.answers))
        return turn.finish(Trigger.SUBMIT, State.REVIEW)
    turn.event("submitted")
    return turn.finish(Trigger.SUBMIT, State.SUBMITTED)
