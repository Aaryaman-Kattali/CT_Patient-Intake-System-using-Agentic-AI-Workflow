from pathlib import Path

import pytest

from app.workflow import commands as c
from app.workflow.metrics import repeated_questions
from app.workflow.states import State
from app.workflow.understanding import ReplyKind
from tests.workflow_helpers import (
    FI,
    FI_CHILD_BOOK,
    FI_SELF_BOOK,
    PR_BOOK,
    Driver,
    make_service,
    question_marks,
    understood,
)

A = ReplyKind.ANSWER


@pytest.fixture
def d(tmp_path: Path) -> Driver:
    return Driver(make_service(tmp_path / "intake.db"))


def _to(d: Driver, field_id: str, book: dict[str, str] = FI_SELF_BOOK) -> None:
    """Answer from the book until the given field's question is showing."""
    if d.view.state is State.GREETING:
        d.send(c.Start())
    for _ in range(30):
        q = d.view.question
        assert q is not None, d.view
        if q.field_id == field_id and q.kind == "field":
            return
        d.answer(book[q.field_id])
    raise AssertionError(f"never reached {field_id}")


# --- whole paths --------------------------------------------------------------


@pytest.mark.parametrize(
    "book", [FI_SELF_BOOK, FI_CHILD_BOOK, PR_BOOK], ids=["fi_self", "fi_child", "pr"]
)
def test_full_path_reaches_review_and_submits(d: Driver, book: dict[str, str]) -> None:
    view = d.run(book)
    assert view.review is not None
    assert view.review.can_submit
    assert {row.field_id for row in view.review.answered} == set(book)
    assert d.send(c.Submit()).state is State.SUBMITTED
    assert repeated_questions(d.events()) == 0


def test_greeting_says_about_12_questions_and_can_stop(d: Driver) -> None:
    assert d.view.state is State.GREETING
    assert d.view.question is None
    assert "This form has about 12 questions." in d.view.info
    assert [a.id for a in d.view.actions] == ["start"]


def test_values_are_normalized_and_shown_back(d: Driver) -> None:
    view = d.run(PR_BOOK)
    assert view.review is not None
    shown = {row.field_id: row.display for row in view.review.answered}
    assert shown["phone"] == "(202) 555-0143"
    assert shown["date_of_birth"] == "February 3, 2001"


def test_progress_counts_the_exact_path(d: Driver) -> None:
    _to(d, "full_name")
    assert d.view.progress.exact
    assert d.view.progress.about_total == 11  # FI, for me
    assert d.view.progress.answered == 2


# --- intake type ----------------------------------------------------------------


def test_intake_type_not_sure_shows_explanation_then_same_buttons(d: Driver) -> None:
    d.send(c.Start())
    view = d.choose("not_sure")
    assert view.state is State.CHOOSE_INTAKE_TYPE
    assert view.question is not None
    assert view.question.field_id == "intake_type"
    assert view.info[0].startswith("If you are a health worker")
    assert "intake_type" not in {e.field_id for e in d.events() if e.type.startswith("field_")}


# --- extras (P5) --------------------------------------------------------------


def test_extra_value_is_confirmed_not_silently_accepted(d: Driver) -> None:
    _to(d, "full_name")
    u = understood(A, ("full_name", "Alex Rivera"), ("date_of_birth", "May 4 2004"))
    view = d.text("Alex Rivera, born May 4 2004", u)
    assert view.acknowledgement == "Saved."
    assert view.question is not None
    assert view.question.kind == "confirm_extra"
    assert view.question.text == "Date of birth: May 4, 2004. Is that right?"
    view = d.choose("yes")
    assert view.question is not None
    assert view.question.field_id != "date_of_birth"  # skipped: already answered
    assert d.question_count("date_of_birth") == 0


def test_rejected_extra_is_asked_normally_later(d: Driver) -> None:
    _to(d, "full_name")
    d.text(
        "Alex Rivera, May 4 2004",
        understood(A, ("full_name", "Alex Rivera"), ("date_of_birth", "May 4 2004")),
    )
    view = d.choose("no")
    assert view.question is not None
    assert view.question.field_id == "date_of_birth"
    assert view.question.kind == "field"


def test_inferred_value_for_asked_field_needs_confirmation(d: Driver) -> None:
    _to(d, "relationship")
    u = understood(A, ("relationship", "my son", "inferred"))
    u = u.model_copy(update={"proposals": (u.proposals[0].model_copy(update={"value": "child"}),)})
    view = d.text("my son", u)
    assert view.question is not None
    assert view.question.kind == "confirm_value"
    assert view.question.text == "Who this form is for: My child. Is that right?"
    d.choose("yes")
    assert d.events()[-1].type == "question_shown"


def test_extra_for_family_only_field_dropped_for_referral(d: Driver) -> None:
    _to(d, "full_name", PR_BOOK)
    u = understood(A, ("full_name", "Sam Park"), ("relationship", "Me"))
    view = d.text("Sam Park, it is for me", u)
    assert view.question is not None
    assert view.question.kind == "field"
    rejected = [e for e in d.events() if e.type == "proposal_rejected"]
    assert rejected[0].field_id == "relationship"
    assert rejected[0].payload == {"reason": "unknown_field"}


def test_hallucinated_value_is_not_saved(d: Driver) -> None:
    _to(d, "full_name")
    bad = understood(A, ("full_name", "Alex Rivera"))
    bad = bad.model_copy(
        update={"proposals": (bad.proposals[0].model_copy(update={"value": "Someone Else"}),)}
    )
    view = d.text("Alex Rivera", bad)
    assert view.info == ("I did not understand. Here is the question again.",)
    assert view.question is not None
    assert view.question.field_id == "full_name"


# --- conflicts, corrections, undo (Q7) -------------------------------------------


def _answered_dob(d: Driver) -> None:
    _to(d, "date_of_birth")
    d.text("May 4, 2004")


def test_unannounced_new_value_asks_which_is_correct(d: Driver) -> None:
    _answered_dob(d)  # now showing: preferred contact method
    view = d.text("I was born June 4 2004", understood(A, ("date_of_birth", "June 4 2004")))
    assert view.question is not None
    assert view.question.kind == "conflict"
    assert view.question.text == (
        "Earlier you said May 4, 2004. Now you said June 4, 2004. Which one is correct?"
    )
    assert [o.label for o in view.question.options] == [
        "May 4, 2004",
        "June 4, 2004",
        "Neither",
        "I'm not sure",
    ]
    d.choose("new")
    snap = d.service._repo.load(d.id)
    assert snap is not None
    assert snap.answers["date_of_birth"].value == "2004-06-04"


def test_inferred_change_goes_to_conflict_even_when_marked_correction(d: Driver) -> None:
    _answered_dob(d)
    u = understood(ReplyKind.CORRECTION, ("date_of_birth", "June 4 2004", "inferred"))
    view = d.text("it was June 4 2004 I think", u)
    assert view.question is not None
    assert view.question.kind == "conflict"


def test_not_sure_on_conflict_keeps_earlier_value_and_flags_both(d: Driver) -> None:
    _answered_dob(d)
    d.text("June 4 2004", understood(A, ("date_of_birth", "June 4 2004")))
    assert d.view.question is not None
    assert "not_sure" in [o.id for o in d.view.question.options]
    d.text("I don't know", understood(ReplyKind.DONT_KNOW))
    snap = d.service._repo.load(d.id)
    assert snap is not None
    dob = snap.answers["date_of_birth"]
    assert (dob.value, dob.unresolved_other) == ("2004-05-04", "June 4, 2004")
    unresolved = [e for e in d.events() if e.type == "conflict_unresolved"]
    assert unresolved[0].payload == {"kept": "May 4, 2004", "other": "June 4, 2004"}


def test_later_change_clears_unresolved_conflict(d: Driver) -> None:
    _answered_dob(d)
    d.text("June 4 2004", understood(A, ("date_of_birth", "June 4 2004")))
    d.choose("not_sure")
    d.text(
        "sorry, it is May 14 2004",
        understood(ReplyKind.CORRECTION, ("date_of_birth", "May 14 2004")),
    )
    snap = d.service._repo.load(d.id)
    assert snap is not None
    assert snap.answers["date_of_birth"].unresolved_other is None


def test_neither_asks_the_field_again_now(d: Driver) -> None:
    _answered_dob(d)
    d.text("June 4 2004", understood(A, ("date_of_birth", "June 4 2004")))
    view = d.choose("neither")
    assert view.question is not None
    assert (view.question.field_id, view.question.kind) == ("date_of_birth", "field")
    assert repeated_questions(d.events()) == 0  # the user asked for it: not a repeat


def test_quoted_correction_saves_and_offers_undo(d: Driver) -> None:
    _answered_dob(d)
    u = understood(ReplyKind.CORRECTION, ("date_of_birth", "May 14 2004"))
    view = d.text("sorry, my birthday is May 14 2004", u)
    assert view.acknowledgement == "Updated: date of birth is May 14, 2004."
    assert "undo" in [a.id for a in view.actions]
    view = d.send(c.Undo())
    assert view.acknowledgement == "Changed back: date of birth is May 4, 2004."
    assert d.service._repo.load(d.id).answers["date_of_birth"].value == "2004-05-04"  # type: ignore[union-attr]


def test_ambiguous_date_asks_with_two_buttons(d: Driver) -> None:
    _to(d, "date_of_birth")
    view = d.text("04/05/2004")
    assert view.question is not None
    assert view.question.kind == "date_choice"
    assert view.question.text == "Which date do you mean?"
    assert [o.label for o in view.question.options] == ["April 5, 2004", "May 4, 2004"]
    d.choose("2004-05-04")
    assert d.service._repo.load(d.id).answers["date_of_birth"].value == "2004-05-04"  # type: ignore[union-attr]


# --- retries, skip, not sure ------------------------------------------------------


def test_unreadable_answer_retries_calmly_then_offers_a_way_out(d: Driver) -> None:
    _to(d, "date_of_birth")
    view = d.text("sometime in spring")
    assert view.info == ("I could not read that as a date.", "Here is an example: May 4, 2004.")
    d.text("no idea of the format")
    view = d.text("spring")
    assert "We can come back to this question later." in view.info
    assert {"answer_later", "talk_to_a_person"} <= {a.id for a in view.actions}
    view = d.send(c.Skip())
    assert view.acknowledgement == "You can answer this later."


def test_skip_optional_is_final_and_defer_needed_goes_to_review(d: Driver) -> None:
    view = d.run({k: v for k, v in FI_SELF_BOOK.items() if k not in {"gender", "date_of_birth"}})
    assert view.review is not None
    missing = {m.field_id: m for m in view.review.missing}
    assert set(missing) == {"date_of_birth"}
    assert [a.id for a in missing["date_of_birth"].actions] == ["answer_now", "mark_unknown"]
    assert view.review.can_submit


def test_optional_not_sure_is_final(d: Driver) -> None:
    _to(d, "gender")
    d.choose("not_sure")
    assert d.view.state is State.REVIEW
    assert d.view.review is not None
    assert "gender" not in {m.field_id for m in d.view.review.missing}


# --- other reply kinds ------------------------------------------------------------


@pytest.mark.parametrize(
    ("kind", "info"),
    [
        (ReplyKind.OFF_TOPIC, "I can only help with this form."),
        (
            ReplyKind.UNSAFE,
            "I can only use the information for this form. I cannot send or share anything else.",
        ),
    ],
)
def test_off_topic_and_unsafe_keep_the_same_question(d: Driver, kind: ReplyKind, info: str) -> None:
    _to(d, "full_name")
    before = d.service._repo.load(d.id)
    view = d.text("whatever", understood(kind))
    assert view.info == (info,)
    assert view.question is not None
    assert view.question.field_id == "full_name"
    after = d.service._repo.load(d.id)
    assert before is not None
    assert after is not None
    assert before.answers == after.answers


def test_why_and_meaning_show_fixed_text(d: Driver) -> None:
    _to(d, "date_of_birth")
    view = d.text("why?", understood(ReplyKind.CLARIFICATION, clarification="why"))
    assert view.info == ("This helps us make sure we have the right person.",)
    view = d.text("what?", understood(ReplyKind.CLARIFICATION, clarification="meaning"))
    assert view.info == ("Type the month, the day and the year.",)


def test_overwhelm_hides_the_question_until_keep_going(d: Driver) -> None:
    _to(d, "full_name")
    view = d.text("this is too much", understood(ReplyKind.DISTRESS, distress_level="overwhelmed"))
    assert view.question is None
    assert [a.id for a in view.actions][:3] == ["take_a_break", "talk_to_a_person", "keep_going"]
    view = d.send(c.KeepGoing())
    assert view.question is not None
    assert view.question.field_id == "full_name"


def test_crisis_shows_fixed_region_text_and_needs_human(d: Driver) -> None:
    _to(d, "full_name")
    view = d.text("...", understood(ReplyKind.DISTRESS, distress_level="crisis"))
    assert view.state is State.NEEDS_HUMAN
    assert "If you or someone else is in danger now, call 911." in view.info
    view = d.send(c.ContinueAlone())
    assert view.state is State.COLLECTING
    assert view.question is not None


def test_pause_gives_a_code_and_resume_by_code_restores_the_place(d: Driver) -> None:
    _to(d, "date_of_birth")
    view = d.send(c.Pause())
    assert view.state is State.PAUSED
    assert view.info[-1] == "Write this code down."
    code = view.resume_code
    assert code is not None
    assert d.service.find_by_resume_code(code.lower().replace("-", " ")) == d.id
    assert d.service.find_by_resume_code("AAA-AAA") != d.id
    view = d.send(c.Resume())
    assert view.state is State.COLLECTING
    assert view.question is not None
    assert view.question.field_id == "date_of_birth"


def test_typed_pause_request_pauses(d: Driver) -> None:
    _to(d, "full_name")
    view = d.text("I need to stop for now", understood(ReplyKind.PAUSE))
    assert view.state is State.PAUSED


def test_welcome_back_uses_preferred_name(d: Driver) -> None:
    d.run(FI_SELF_BOOK)
    d.send(c.Pause())
    assert d.send(c.Resume()).info == ("Welcome back, Alex.",)


# --- review --------------------------------------------------------------------------


def test_review_edit_returns_to_review(d: Driver) -> None:
    d.run(FI_SELF_BOOK)
    view = d.send(c.EditField(field_id="date_of_birth"))
    assert view.question is not None
    assert view.question.field_id == "date_of_birth"
    view = d.text("June 1, 2004")
    assert view.state is State.REVIEW
    assert repeated_questions(d.events()) == 0


def test_must_have_blocks_submit_until_answered(d: Driver) -> None:
    view = d.run({k: v for k, v in FI_SELF_BOOK.items() if k != "full_name"})
    assert view.review is not None
    assert not view.review.can_submit
    view = d.send(c.Submit())
    assert view.state is State.REVIEW
    assert "Some answers are still needed before you can send this form." in view.info
    d.send(c.EditField(field_id="full_name"))
    d.text("Alex Rivera")
    assert d.send(c.Submit()).state is State.SUBMITTED


def test_mark_unknown_then_submit(d: Driver) -> None:
    d.run({k: v for k, v in FI_SELF_BOOK.items() if k != "date_of_birth"})
    view = d.send(c.MarkUnknown(field_id="date_of_birth"))
    assert view.review is not None
    missing = {m.field_id: m for m in view.review.missing}
    assert missing["date_of_birth"].state == "Not known"
    assert d.send(c.Submit()).state is State.SUBMITTED


# --- buttons never call the LLM ------------------------------------------------------


def test_buttons_and_typed_yes_no_never_call_the_llm(d: Driver) -> None:
    d.send(c.Start())
    d.choose(FI)
    d.choose("me")
    d.text(
        "Alex Rivera, May 4 2004",
        understood(A, ("full_name", "Alex Rivera"), ("date_of_birth", "May 4 2004")),
    )
    calls_before = len(d.fake.calls)
    view = d.text("yes")  # typed yes/no is matched deterministically
    assert len(d.fake.calls) == calls_before
    assert view.question is not None
    assert view.question.field_id == "preferred_contact_method"
    d.choose("email")
    assert len(d.fake.calls) == calls_before


def test_every_turn_shows_at_most_one_question(d: Driver) -> None:
    views = [d.view, d.send(c.Start())]
    while d.view.question is not None:
        views.append(d.answer(FI_CHILD_BOOK[d.view.question.field_id]))
    assert all(question_marks(v) <= 1 for v in views)
