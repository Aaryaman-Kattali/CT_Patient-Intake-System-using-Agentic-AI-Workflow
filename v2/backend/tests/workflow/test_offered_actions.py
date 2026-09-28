"""Invariant: everything a Turn offers the user works, from every reachable state.

Hypothesis walks random paths through the pure engine. At every step it collects every action
the current Turn offers (action buttons, option buttons, Skip / Answer later, a typed answer,
a typed answer with an extra value, and each review button) and applies each one to the
current snapshot. Every one must be applied without an error (e.g. IllegalTransition), and
must not be refused silently. This would have caught the review-screen crash found in Phase 7.
"""

from uuid import uuid4

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.domain.types import InputType
from app.workflow import commands as c
from app.workflow.engine import Applied, Rejected, handle
from app.workflow.snapshot import Snapshot
from app.workflow.states import State
from app.workflow.understanding import ReplyKind, ReplyUnderstanding
from app.workflow.view import TurnView, render
from tests.workflow_helpers import FI_CHILD_BOOK, PR_BOOK, EngineHarness, understood

Offer = tuple[str, c.Command, ReplyUnderstanding | None]

BOOK = {**PR_BOOK, **FI_CHILD_BOOK}  # a typed value for every text field
# Different values for already-answered fields, so extras can create conflicts.
OTHER = {"full_name": "Sam Park", "date_of_birth": "June 4, 2004", "phone": "202-555-0143"}

ACTION_COMMANDS: dict[str, c.Command] = {
    "start": c.Start(),
    "resume": c.Resume(),
    "continue_alone": c.ContinueAlone(),
    "take_a_break": c.Pause(),
    "keep_going": c.KeepGoing(),
    "talk_to_a_person": c.TalkToPerson(),
    "undo": c.Undo(),
    "answer_later": c.Skip(),
    "submit": c.Submit(),
}


def offered(view: TurnView) -> list[Offer]:
    """Everything the frontend shows as something to press or type, for this Turn."""
    offers: list[Offer] = []
    for action in view.actions:
        assert action.id in ACTION_COMMANDS, f"offered action with no command: {action.id}"
        offers.append((f"action:{action.id}", ACTION_COMMANDS[action.id], None))
    q = view.question
    if q is not None:
        if q.input_type is InputType.CHOICE:
            for o in q.options:
                typed = "Some words" if o.free_text else None
                offers.append((f"choose:{o.id}", c.Choose(option_id=o.id, extra_text=typed), None))
        else:
            value = BOOK.get(q.field_id, "Some words")
            offers.append(
                ("text", c.Text(text=value), understood(ReplyKind.ANSWER, (q.field_id, value)))
            )
            other = next((f for f in OTHER if f != q.field_id), "full_name")
            extra = understood(
                ReplyKind.ANSWER_PLUS_EXTRA, (q.field_id, value), (other, OTHER[other])
            )
            offers.append(("text+extra", c.Text(text=f"{value}, {OTHER[other]}"), extra))
            fix = understood(ReplyKind.CORRECTION, (q.field_id, value), (other, OTHER[other]))
            offers.append(("text+correction", c.Text(text=f"{value}, sorry {OTHER[other]}"), fix))
        if q.kind == "field" and (q.can_skip or q.can_defer):
            offers.append(("skip", c.Skip(), None))
    if view.review is not None:
        for row in view.review.answered:
            offers.append((f"change:{row.field_id}", c.EditField(field_id=row.field_id), None))
        for item in view.review.missing:
            for action in item.actions:
                cmd: c.Command = (
                    c.MarkUnknown(field_id=item.field_id)
                    if action.id == "mark_unknown"
                    else c.EditField(field_id=item.field_id)
                )
                offers.append((f"{action.id}:{item.field_id}", cmd, None))
    return offers


def _check_all(snap: Snapshot, view: TurnView, harness: EngineHarness) -> list[Offer]:
    offers = offered(view)
    for name, command, u in offers:
        result = handle(snap, command, harness.config, u)  # raises on an illegal transition
        assert not (isinstance(result, Rejected) and not result.notes.info), (
            f"{name} offered in {snap.state} but refused silently: {result.reason}"
        )
    return offers


@settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(picks=st.lists(st.integers(min_value=0, max_value=10_000), min_size=1, max_size=45))
def test_every_offered_action_works_from_every_reachable_state(picks: list[int]) -> None:
    harness = EngineHarness(Snapshot(id=uuid4(), state=State.GREETING))
    view = harness.view
    for pick in picks:
        offers = _check_all(harness.snap, view, harness)
        if not offers:  # SUBMITTED: nothing to press
            assert harness.snap.state is State.SUBMITTED
            return
        _, command, u = offers[pick % len(offers)]
        result = handle(harness.snap, command, harness.config, u)
        if isinstance(result, Applied):
            harness.snap = result.snapshot
            view = render(result.snapshot, result.notes)


def test_review_edit_paths_are_covered() -> None:
    """The Phase 7 crash path, explicitly: review -> change the kind of form -> answer."""
    harness = EngineHarness(Snapshot(id=uuid4(), state=State.GREETING))
    harness.send(c.Start())
    while harness.snap.state is not State.REVIEW:
        q = harness.view.question
        assert q is not None
        if q.input_type is InputType.CHOICE:
            first = q.options[0]
            harness.send(c.Choose(option_id=first.id, extra_text="x" if first.free_text else None))
        elif q.can_skip or q.can_defer:
            harness.send(c.Skip())
        else:
            value = BOOK[q.field_id]
            harness.send(c.Text(text=value), understood(ReplyKind.ANSWER, (q.field_id, value)))
    for _ in range(3):
        _check_all(harness.snap, harness.view, harness)
        harness.send(c.EditField(field_id="intake_type"))
        _check_all(harness.snap, harness.view, harness)
        harness.send(c.Choose(option_id="family_inquiry"))
        assert harness.snap.state is State.REVIEW
