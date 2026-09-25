"""Named regression tests for audit items #2-#5, B11 and the Phase 4 requirements."""

import inspect
from pathlib import Path
from uuid import UUID

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError

from app.config import Settings
from app.services import persistence
from app.services.persistence import IntakeRepository
from app.workflow import commands as c
from app.workflow.metrics import repeated_questions
from app.workflow.snapshot import Snapshot
from app.workflow.states import State
from app.workflow.transitions import TABLE, IllegalTransition, Trigger, check
from app.workflow.understanding import ReplyKind
from tests.conftest import REPO_ROOT
from tests.workflow_helpers import (
    FI_CHILD_BOOK,
    FI_SELF_BOOK,
    PR_BOOK,
    Driver,
    EngineHarness,
    make_service,
    question_marks,
    understood,
)

# --- #3: nothing is lost when the user stops -----------------------------------------


def test_partial_intake_survives_restart(tmp_path: Path) -> None:
    db = tmp_path / "intake.db"
    first = Driver(make_service(db))
    first.send(c.Start())
    first.choose(FI_SELF_BOOK["intake_type"])  # question 1
    first.choose("me")  # question 2
    first.text("Alex Rivera")  # question 3
    intake_id = first.id
    first.service._repo._engine.dispose()
    del first

    # A brand-new app: new engine, new repository, new service, same file.
    second = Driver(make_service(db), intake_id)
    view = second.view
    assert view.question is not None
    assert view.question.field_id == "date_of_birth"  # the 4th question
    snap = second.service._repo.load(intake_id)
    assert snap is not None
    assert {k: v.value for k, v in snap.answers.items()} == {
        "intake_type": "family_inquiry",
        "relationship": "me",
        "full_name": "Alex Rivera",
    }


def test_each_accepted_answer_is_committed_before_response(tmp_path: Path) -> None:
    db = tmp_path / "intake.db"
    d = Driver(make_service(db))
    d.send(c.Start())
    d.choose("provider_referral")
    other_connection = IntakeRepository(persistence.create_db_engine(f"sqlite:///{db.as_posix()}"))
    snap = other_connection.load(d.id)
    assert snap is not None
    assert snap.answers["intake_type"].value == "provider_referral"


# --- stale tabs and double clicks -----------------------------------------------------


def test_duplicate_reply_does_not_save_twice_or_skip(tmp_path: Path) -> None:
    service = make_service(tmp_path / "intake.db")
    d = Driver(service)
    d.send(c.Start())
    d.choose("family_inquiry")
    turn = d.view.turn
    first = service.handle(d.id, turn, c.Choose(option_id="me"))
    second = service.handle(d.id, turn, c.Choose(option_id="me"))  # double click
    assert (first.status, second.status) == ("applied", "stale")
    assert second.view is not None
    assert second.view.question is not None
    assert second.view.question.field_id == "full_name"  # not skipped past
    accepted = [
        e for e in d.events() if e.type == "field_accepted" and e.field_id == "relationship"
    ]
    assert len(accepted) == 1


def test_second_tab_with_old_turn_is_rejected_and_can_refresh(tmp_path: Path) -> None:
    service = make_service(tmp_path / "intake.db")
    tab_a = Driver(service)
    tab_a.send(c.Start())
    tab_b = Driver(service, tab_a.id)  # opened at the same turn
    tab_a.choose("provider_referral")
    tab_b.send(c.Choose(option_id="family_inquiry"), expect="stale")
    assert tab_b.view.question is not None
    assert tab_b.view.question.field_id == "full_name"  # B now sees A's progress
    snap = service._repo.load(tab_a.id)
    assert snap is not None
    assert snap.answers["intake_type"].value == "provider_referral"


# --- undo only on the next turn ---------------------------------------------------------


def _corrected(tmp_path: Path) -> Driver:
    d = Driver(make_service(tmp_path / "intake.db"))
    d.send(c.Start())
    d.choose("family_inquiry")
    d.choose("me")
    d.text("Alex Rivera")
    d.text("May 4, 2004")
    d.text("x", understood(ReplyKind.CORRECTION, ("date_of_birth", "May 14 2004")))
    return d


def test_undo_restores_previous_value(tmp_path: Path) -> None:
    d = _corrected(tmp_path)
    d.send(c.Undo())
    snap = d.service._repo.load(d.id)
    assert snap is not None
    assert snap.answers["date_of_birth"].value == "2004-05-04"


def test_undo_rejected_after_another_turn(tmp_path: Path) -> None:
    d = _corrected(tmp_path)
    d.choose("email")  # a different reply first
    view = d.send(c.Undo(), expect="rejected")
    assert "undo" not in [a.id for a in view.actions]
    snap = d.service._repo.load(d.id)
    assert snap is not None
    assert snap.answers["date_of_birth"].value == "2004-05-14"


def test_undo_without_correction_is_rejected(tmp_path: Path) -> None:
    d = Driver(make_service(tmp_path / "intake.db"))
    d.send(c.Start())
    d.send(c.Undo(), expect="rejected")


def test_correction_requires_quoted_value(tmp_path: Path) -> None:
    d = _corrected(tmp_path)
    d.send(c.Undo())
    view = d.text(
        "x", understood(ReplyKind.CORRECTION, ("date_of_birth", "June 4 2004", "inferred"))
    )
    assert view.question is not None
    assert view.question.kind == "conflict"  # never a silent overwrite


# --- intake_events is append-only ---------------------------------------------------------


def test_intake_events_append_only(tmp_path: Path) -> None:
    public = [n for n, _ in inspect.getmembers(IntakeRepository, inspect.isfunction)]
    event_writers = [n for n in public if "event" in n and n != "events"]
    assert event_writers == []  # the only event method is the reader
    source = inspect.getsource(persistence)
    assert "update(EventRow" not in source
    assert "delete(EventRow" not in source

    d = Driver(make_service(tmp_path / "intake.db"))
    d.send(c.Start())
    engine = d.service._repo._engine
    for statement in (
        "UPDATE intake_events SET type = 'x'",
        "DELETE FROM intake_events",
    ):
        with (
            pytest.raises((IntegrityError, OperationalError), match="append-only"),
            engine.begin() as conn,
        ):
            conn.execute(text(statement))
    assert len(d.events()) >= 2


# --- storage location ---------------------------------------------------------------------


def test_default_db_path_is_outside_repo() -> None:
    url = Settings().database_url
    path = Path(url.removeprefix("sqlite:///"))
    assert path.is_absolute()
    assert not path.resolve().is_relative_to(REPO_ROOT.resolve())


def test_db_path_comes_from_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "from-env" / "x.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{target.as_posix()}")
    persistence.create_db_engine(Settings().database_url)
    assert target.exists()


# --- #5: isolation and ids -------------------------------------------------------------------


def test_concurrent_intakes_are_isolated(tmp_path: Path) -> None:
    service = make_service(tmp_path / "intake.db")
    a, b = Driver(service), Driver(service)
    for d in (a, b):
        d.send(c.Start())
    a.choose("family_inquiry")
    b.choose("provider_referral")
    a.choose("me")
    b.text("Sam Park")
    a.text("Alex Rivera")
    snap_a, snap_b = service._repo.load(a.id), service._repo.load(b.id)
    assert snap_a is not None
    assert snap_b is not None
    assert snap_a.answers["full_name"].value == "Alex Rivera"
    assert snap_b.answers["full_name"].value == "Sam Park"
    assert "relationship" not in snap_b.answers


def test_intake_ids_are_uuid4(tmp_path: Path) -> None:
    service = make_service(tmp_path / "intake.db")
    ids = {service.create().intake_id for _ in range(5)}
    assert len(ids) == 5
    assert all(isinstance(i, UUID) and i.version == 4 for i in ids)


def test_token_and_resume_code_are_stored_hashed(tmp_path: Path) -> None:
    service = make_service(tmp_path / "intake.db")
    created = service.create()
    assert service.verify_token(created.intake_id, created.token)
    assert not service.verify_token(created.intake_id, "wrong")
    assert service._repo.token_hash(created.intake_id) != created.token


# --- #4 and the intake-type clarification ---------------------------------------------------


@pytest.mark.parametrize("book", [FI_SELF_BOOK, FI_CHILD_BOOK, PR_BOOK])
def test_intake_type_asked_once(tmp_path: Path, book: dict[str, str]) -> None:
    d = Driver(make_service(tmp_path / "intake.db"))
    d.run(book)
    assert d.question_count("intake_type") == 1


def test_intake_type_not_sure_is_clarification_not_repeat(tmp_path: Path) -> None:
    d = Driver(make_service(tmp_path / "intake.db"))
    d.send(c.Start())
    view = d.choose("not_sure")
    assert view.question is not None
    assert view.question.field_id == "intake_type"
    assert len(view.info) == 1
    assert [o.id for o in view.question.options][:2] == ["family_inquiry", "provider_referral"]
    assert not any(e.type.startswith("field_") for e in d.events())  # nothing saved
    d.run(FI_SELF_BOOK)
    events = d.events()
    assert any(e.type == "clarification_shown" and e.field_id == "intake_type" for e in events)
    assert repeated_questions(events) == 0


# --- #2: one question per turn, never a repeat (property test) -------------------------------

_BOOKS = [FI_SELF_BOOK, FI_CHILD_BOOK, PR_BOOK]


@settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(data=st.data(), book=st.sampled_from(_BOOKS))
def test_turn_has_at_most_one_question_and_no_repeats(
    data: st.DataObject, book: dict[str, str]
) -> None:
    h = EngineHarness(Snapshot(id=UUID(int=4), state=State.GREETING))
    h.send(c.Start())
    for _ in range(45):
        assert question_marks(h.view) <= 1
        q = h.view.question
        if h.view.state is State.PAUSED:
            h.send(c.Resume())
            continue
        if h.view.state is State.NEEDS_HUMAN:
            h.send(c.ContinueAlone())
            continue
        if q is None:
            if h.view.state is State.REVIEW:
                break
            h.send(c.KeepGoing())
            continue
        action = data.draw(
            st.sampled_from(
                [
                    "answer",
                    "answer",
                    "answer",
                    "skip",
                    "not_sure",
                    "off_topic",
                    "why",
                    "pause",
                    "extra",
                    "overwhelmed",
                    "no",
                ]
            )
        )
        _act(h, action, q.field_id, q.kind, book)
    assert repeated_questions(h.events) == 0


def _act(h: EngineHarness, action: str, field_id: str, kind: str, book: dict[str, str]) -> None:
    if kind != "field":
        option = "no" if action == "no" else h.view.question.options[0].id  # type: ignore[union-attr]
        h.send(c.Choose(option_id=option))
        return
    value = book.get(field_id)
    match action:
        case "skip":
            h.send(c.Skip())
        case "not_sure" if any(o.id == "not_sure" for o in h.view.question.options):  # type: ignore[union-attr]
            h.send(c.Choose(option_id="not_sure"))
        case "off_topic":
            h.send(c.Text(text="hi"), understood(ReplyKind.OFF_TOPIC))
        case "why":
            h.send(c.Text(text="why"), understood(ReplyKind.CLARIFICATION, clarification="why"))
        case "pause":
            h.send(c.Pause(resume_code="ABCD 2345", resume_code_hash="h"))
        case "overwhelmed":
            h.send(c.Text(text="..."), understood(ReplyKind.DISTRESS, distress_level="overwhelmed"))
        case "extra" if value is not None:
            other = next((k for k in book if k not in (field_id, "intake_type")), None)
            props = [(field_id, value)] + ([(other, book[other])] if other else [])
            h.send(c.Text(text=value), understood(ReplyKind.ANSWER, *props))
        case _ if value is None:
            h.send(c.Skip())
        case _ if h.view.question.input_type.value == "choice":  # type: ignore[union-attr]
            h.send(c.Choose(option_id=value))
        case _:
            h.send(c.Text(text=value), understood(ReplyKind.ANSWER, (field_id, value)))


# --- state machine table ------------------------------------------------------------------------


def test_illegal_transitions_raise() -> None:
    for state in State:
        for trigger in Trigger:
            allowed_targets = TABLE.get((state, trigger), frozenset())
            for target in State:
                if target in allowed_targets:
                    check(state, trigger, target)
                else:
                    with pytest.raises(IllegalTransition):
                        check(state, trigger, target)


def test_submitted_is_terminal(tmp_path: Path) -> None:
    d = Driver(make_service(tmp_path / "intake.db"))
    d.run(PR_BOOK)
    d.send(c.Submit())
    for command in (
        c.Start(),
        c.Skip(),
        c.Pause(),
        c.Undo(),
        c.Choose(option_id="yes"),
        c.Submit(),
    ):
        d.send(command, expect="rejected")
    assert d.refresh().state is State.SUBMITTED


def test_paused_only_accepts_resume(tmp_path: Path) -> None:
    d = Driver(make_service(tmp_path / "intake.db"))
    d.send(c.Start())
    d.send(c.Pause())
    for command in (c.Choose(option_id="family_inquiry"), c.Skip(), c.Submit(), c.Text(text="hi")):
        d.send(command, expect="rejected")
    assert d.send(c.Resume()).state is State.CHOOSE_INTAKE_TYPE
