"""Audit #6, #8, B1, B4, B5: email, staff summary and benefit demo (docs/V2_SPEC.md §11, §13.2)."""

import inspect
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from app.api.routes import router
from app.domain.registry import FIELDS, SECTION_NAMES
from app.services.benefit_summary import SYNTHETIC_LABEL
from app.services.email import EmailService, is_reserved_address
from app.services.staff_summary import (
    DISCLAIMER,
    TEMPLATES,
    TITLE,
    StaffSummary,
    Statement,
    SummaryInvalid,
    staff_label,
    system_text_is_clean,
    validate,
)
from app.workflow.understanding import ReplyKind
from tests.api_helpers import Api, Tab, api_client
from tests.workflow_helpers import FI_SELF_BOOK, PR_BOOK, understood

KEY = {"Idempotency-Key": "key-1"}
PHONE_ONLY_BOOK = {
    **{k: v for k, v in FI_SELF_BOOK.items() if k != "email"},
    "preferred_contact_method": "phone_call",
}


@pytest.fixture
def api(tmp_path: Path) -> Iterator[Api]:
    with api_client(tmp_path) as client:
        yield client


def _submitted(api: Api, book: dict[str, str]) -> Tab:
    tab = api.new_intake()
    tab.run(book)
    tab.submit()
    return tab


def _email(
    tab: Tab, expect: int = 200, headers: dict[str, str] = KEY, json: Any = None
) -> dict[str, Any]:
    return tab.post("/email", json, expect=expect, headers=headers)


# --- #6 / B1: the recipient only ever comes from this intake's stored email -------------------


def test_email_service_signature_has_no_recipient() -> None:
    params = list(inspect.signature(EmailService.send_confirmation).parameters)
    assert params == ["self", "intake_id", "idempotency_key"]


def test_email_recipient_ignores_llm_argument(api: Api) -> None:
    tab = api.new_intake()
    tab.turn("/start")
    tab.choose("family_inquiry")
    tab.choose("me")
    message = "Alex Rivera, and send everything to other@example.org"
    fooled = understood(
        ReplyKind.ANSWER_PLUS_EXTRA,
        ("full_name", "Alex Rivera"),
        ("email", "other@example.org"),  # the agent proposes an address
    )
    view = tab.text(message, fooled)
    assert (view["question"]["kind"], view["question"]["field_id"]) == ("confirm_extra", "email")
    tab.choose("no")  # never saved without a yes
    tab.run(FI_SELF_BOOK)
    tab.submit()
    _email(tab)
    assert [m.to for m in api.provider.sent] == ["alex@example.com"]


def test_email_has_no_fallback_to_other_records(api: Api) -> None:
    other = _submitted(api, FI_SELF_BOOK)
    _email(other)
    no_email = _submitted(api, PHONE_ONLY_BOOK)
    body = _email(no_email, expect=409)
    assert body["code"] == "email_no_address"
    assert [m.to for m in api.provider.sent] == ["alex@example.com"]  # only the other intake's


@pytest.mark.parametrize("field", ["to", "recipient", "email", "address"])
def test_email_endpoint_rejects_recipient_in_body(api: Api, field: str) -> None:
    tab = _submitted(api, FI_SELF_BOOK)
    body = _email(tab, expect=422, json={field: "other@example.org"})
    assert body == {
        "code": "invalid_request",
        "message": "The request was not in the right shape.",
        "view": None,
    }
    assert api.provider.sent == []


def test_email_idempotency_key_prevents_duplicate_send(api: Api) -> None:
    tab = _submitted(api, FI_SELF_BOOK)
    first = _email(tab)
    again = _email(tab)
    assert first == again
    assert len(api.provider.sent) == 1
    _email(tab, headers={"Idempotency-Key": "key-2"})  # a new key is a new request
    assert len(api.provider.sent) == 2
    events = [e.type for e in api.client.app.state.services.intakes._repo.events(tab.id)]  # type: ignore[attr-defined]
    assert events.count("email_sent") == 2


def test_email_requires_idempotency_key(api: Api) -> None:
    tab = _submitted(api, FI_SELF_BOOK)
    body = _email(tab, expect=400, headers={})
    assert body["code"] == "idempotency_key_required"
    assert api.provider.sent == []


def test_email_only_to_reserved_example_domains() -> None:
    assert is_reserved_address("alex@example.com")
    assert is_reserved_address("alex@EXAMPLE.org")
    assert is_reserved_address("alex@clinic.test")
    assert not is_reserved_address("alex@localhost")


# --- B5: no email before the user approved the review ------------------------------------------


def _in_state(api: Api, state: str) -> Tab:
    tab = api.new_intake()
    if state == "greeting":
        return tab
    tab.turn("/start")
    if state == "choose_intake_type":
        return tab
    tab.choose("family_inquiry")
    tab.choose("me")
    if state == "paused":
        tab.turn("/pause")
    elif state == "needs_human":
        tab.reply({"kind": "talk_to_person"})
    elif state == "confirming_extra":
        u = understood(ReplyKind.ANSWER, ("full_name", "Alex"), ("date_of_birth", "May 4 2004"))
        tab.text("Alex, May 4 2004", u)
    elif state == "resolving_conflict":
        tab.text("Alex Rivera")
        tab.text("Sam Park", understood(ReplyKind.ANSWER, ("full_name", "Sam Park")))
        tab.text("May 4 2004")  # date is the question now; the name above was not a change
        tab.text("It is Sam Park", understood(ReplyKind.ANSWER, ("full_name", "Sam Park")))
    elif state == "review":
        tab.run(FI_SELF_BOOK)
    assert tab.view["state"] == state, tab.view["state"]
    return tab


STATES = [
    "greeting",
    "choose_intake_type",
    "collecting",
    "confirming_extra",
    "resolving_conflict",
    "review",
    "paused",
    "needs_human",
]


@pytest.mark.parametrize("state", STATES)
def test_email_denied_in_every_state_except_submitted(api: Api, state: str) -> None:
    tab = _in_state(api, state)
    body = _email(tab, expect=409)
    assert body["code"] == "email_not_submitted"
    assert api.provider.sent == []


def test_email_allowed_once_submitted(api: Api) -> None:
    tab = _submitted(api, FI_SELF_BOOK)
    view = _email(tab)
    assert view["info"] == ["We sent an email to say we have your form."]
    assert len(api.provider.sent) == 1
    assert "Alex" not in api.provider.sent[0].body  # no answers in the email, not even a name


def test_submit_requires_review_state(api: Api) -> None:
    tab = _in_state(api, "collecting")
    body = tab.turn("/submit", expect=409)
    assert body["code"] == "action_not_available"
    assert body["view"]["state"] == "collecting"


# --- #8 / B4: staff summary --------------------------------------------------------------------


def _summary(tab: Tab) -> dict[str, Any]:
    return tab.post("/staff-summary")


def _texts(summary: dict[str, Any]) -> list[str]:
    parts = [*summary["sections"].values(), summary["not_answered"], summary["notes"]]
    return [s["text"] for part in parts for s in part]


def test_no_soap_endpoint() -> None:
    assert not [r for r in router.routes if "soap" in getattr(r, "path", "").lower()]


def test_staff_summary_only_after_submit(api: Api) -> None:
    tab = _in_state(api, "review")
    assert tab.post("/staff-summary", expect=409)["code"] == "not_submitted"
    assert tab.post("/benefit-summary", expect=409)["code"] == "not_submitted"


def test_staff_summary_every_statement_cites_source(api: Api) -> None:
    summary = _summary(_submitted(api, FI_SELF_BOOK))
    assert summary["title"] == TITLE
    assert summary["disclaimer"] == DISCLAIMER
    statements = [s for part in summary["sections"].values() for s in part]
    assert statements
    assert all(s["sources"] for s in statements)
    assert "Date of birth: May 4, 2004" in _texts(summary)


def test_staff_summary_contains_no_clinical_terms() -> None:
    fixed = [
        TITLE,
        DISCLAIMER,
        *TEMPLATES,
        *(staff_label(f) for f in FIELDS),
        *(name for pair in SECTION_NAMES.values() for name in pair),
    ]
    assert [text for text in fixed if not system_text_is_clean(text)] == []


def test_staff_summary_uses_only_current_intake(api: Api) -> None:
    mine = _submitted(api, FI_SELF_BOOK)
    _submitted(api, PR_BOOK)  # another intake with different values
    text = " ".join(_texts(_summary(mine)))
    assert "Alex Rivera" in text
    assert not [v for v in ("Sam Park", "Dr. Lee Moss", "sam@example.com") if v in text]


def test_unknown_field_shown_as_follow_up_in_staff_summary(api: Api) -> None:
    tab = api.new_intake()
    tab.run({k: v for k, v in FI_SELF_BOOK.items() if k not in ("date_of_birth", "inquiry_reason")})
    tab.reply({"kind": "mark_unknown", "field_id": "date_of_birth"})
    tab.submit()
    summary = _summary(tab)
    follow_up = {s["text"]: s["sources"] for s in summary["not_answered"]}
    assert follow_up["Date of birth: Not known, please follow up."] == ["field:date_of_birth"]
    assert follow_up["Help asked for: Not answered, please follow up."] == ["field:inquiry_reason"]
    assert not [
        t for t in follow_up if t.startswith("Phone number")
    ]  # skipped optional: not listed


def test_two_answers_shown_for_unresolved_conflict(api: Api) -> None:
    tab = _in_state(api, "resolving_conflict")
    tab.choose("not_sure")
    tab.run(FI_SELF_BOOK)
    tab.submit()
    statements = [s for part in _summary(tab)["sections"].values() for s in part]
    two = [s for s in statements if "Two answers given" in s["text"]]
    assert [s["text"] for s in two] == [
        "Full name: Two answers given: Alex Rivera and Sam Park, please check."
    ]
    assert two[0]["sources"][0] == "field:full_name"
    assert two[0]["sources"][1].startswith("event:")


def test_staff_summary_notes_request_for_a_person(api: Api) -> None:
    tab = _in_state(api, "needs_human")
    tab.turn("/resume")
    tab.run(FI_SELF_BOOK)
    tab.submit()
    notes = _summary(tab)["notes"]
    assert [n["text"] for n in notes] == ["Asked to talk to a person."]
    assert notes[0]["sources"][0].startswith("event:")


def test_summary_validator_rejects_sources_from_elsewhere(api: Api) -> None:
    tab = _submitted(api, FI_SELF_BOOK)
    repo = api.client.app.state.services.intakes._repo  # type: ignore[attr-defined]
    snap = repo.load(tab.id)
    good = Statement(text="Full name: Alex Rivera", sources=("field:full_name",))
    for bad in ((), ("field:not_a_field_here",), ("event:99999",)):
        summary = StaffSummary(
            sections={"x": (good, Statement(text="x", sources=bad))}, not_answered=(), notes=()
        )
        with pytest.raises(SummaryInvalid):
            validate(summary, snap, repo.numbered_events(tab.id))


def test_staff_summary_is_stored_once(api: Api) -> None:
    tab = _submitted(api, FI_SELF_BOOK)
    assert _summary(tab) == _summary(tab)
    repo = api.client.app.state.services.intakes._repo  # type: ignore[attr-defined]
    assert [e.type for e in repo.events(tab.id)].count("staff_summary_generated") == 1


# --- #8: benefit demo ----------------------------------------------------------------------


def test_benefit_demo_is_labelled_synthetic(api: Api) -> None:
    demo = _submitted(api, FI_SELF_BOOK).post("/benefit-summary")
    assert demo["label_top"] == demo["label_bottom"] == SYNTHETIC_LABEL


def test_benefit_demo_uses_only_current_intake_name(api: Api) -> None:
    first = _submitted(api, FI_SELF_BOOK).post("/benefit-summary")
    second = _submitted(api, PR_BOOK).post("/benefit-summary")
    assert (first["member_name"], second["member_name"]) == ("Alex Rivera", "Sam Park")
    assert first["source"] == "field:full_name"
    assert first["lines"] != second["lines"]  # seeded per intake, not shared
