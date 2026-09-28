"""The HTTP API end to end: turns, stale replies, pause/resume, talk to a person, review."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from app.domain import templates as t
from tests.api_helpers import Api, Tab, api_client
from tests.workflow_helpers import FI_CHILD_BOOK, FI_SELF_BOOK, PR_BOOK


@pytest.fixture
def api(tmp_path: Path) -> Iterator[Api]:
    with api_client(tmp_path) as client:
        yield client


@pytest.mark.parametrize(
    "book", [FI_SELF_BOOK, FI_CHILD_BOOK, PR_BOOK], ids=["self", "child", "pr"]
)
def test_full_intake_over_http(api: Api, book: dict[str, str]) -> None:
    tab = api.new_intake()
    assert tab.view["state"] == "greeting"
    tab.run(book)
    view = tab.submit()
    assert view["state"] == "submitted"
    assert view["question"] is None


def test_api_question_is_object_not_list(api: Api) -> None:
    tab = api.new_intake()
    views = [tab.view, tab.turn("/start")]
    while tab.view["question"] is not None:
        views.append(tab.answer(FI_SELF_BOOK[tab.view["question"]["field_id"]]))
    for view in views:
        assert view["question"] is None or isinstance(view["question"], dict)


def test_stale_turn_gets_409_with_current_view(api: Api) -> None:
    tab = api.new_intake()
    old_turn = tab.view["turn"]
    tab.turn("/start")
    body = tab.post("/start", {"turn": old_turn}, expect=409)
    assert body["code"] == "stale_turn"
    assert body["view"]["turn"] == old_turn + 1  # the current view, nothing saved twice


def test_rejected_turn_with_text_for_the_user_is_a_normal_turn(api: Api) -> None:
    tab = api.new_intake()
    _to_full_name(tab)
    view = tab.text("a" * 5000)
    assert view["info"] == ["That message is too long for me to read. You can send a shorter one."]
    assert view["question"]["field_id"] == "full_name"


def test_command_not_allowed_now_is_409(api: Api) -> None:
    tab = api.new_intake()
    body = tab.reply({"kind": "skip"}, expect=409)  # nothing to skip before starting
    assert body["code"] == "action_not_available"
    assert body["view"]["state"] == "greeting"


@pytest.mark.parametrize("token", [None, "wrong-token"])
def test_token_required_and_same_answer_as_unknown_id(api: Api, token: str | None) -> None:
    tab = api.new_intake()
    headers = {"X-Intake-Token": token} if token else {}
    mine = api.client.get(tab.url(), headers=headers)
    unknown = api.client.get("/intakes/00000000-0000-4000-8000-000000000000", headers=headers)
    assert mine.status_code == unknown.status_code == 404
    assert (
        mine.json()
        == unknown.json()
        == {
            "code": "intake_not_found",
            "message": "We could not find this form.",
            "view": None,
            "actions": [],
        }
    )


def test_pause_shows_code_and_resume_returns_to_same_question(api: Api) -> None:
    tab = api.new_intake()
    tab.turn("/start")
    tab.choose("family_inquiry")
    before = tab.view["question"]["field_id"]
    paused = tab.turn("/pause")
    assert paused["state"] == "paused"
    assert paused["resume_code"]
    assert list(paused["info"]) == list(t.PAUSED)
    resumed = tab.turn("/resume")
    assert resumed["question"]["field_id"] == before


def _to_full_name(tab: Tab) -> None:
    tab.turn("/start")
    tab.choose("family_inquiry")
    tab.choose("me")


def test_talk_to_a_person_keeps_answers_and_says_what_happens_next(api: Api) -> None:
    tab = api.new_intake()
    _to_full_name(tab)
    tab.text("Alex Rivera")
    answered_before = tab.api.client.get(tab.url("/review"), headers=tab.headers).json()
    question_before = tab.view["question"]["field_id"]
    view = tab.reply({"kind": "talk_to_person"})
    assert view["state"] == "needs_human"
    assert view["question"] is None
    assert view["info"] == [  # no phone or email yet
        "We have asked a staff member to help you.",
        "We do not have a phone number or email for you yet.",
        "This is a demo. No one will contact you.",
        *t.NEEDS_HUMAN_NO_CONTACT,
    ]
    assert [a["id"] for a in view["actions"]] == ["continue_alone"]
    review = tab.api.client.get(tab.url("/review"), headers=tab.headers).json()
    assert review["review"]["answered"] == answered_before["review"]["answered"]
    back = tab.turn("/resume")  # "Continue on my own"
    assert back["question"]["field_id"] == question_before


def test_talk_to_a_person_with_contact_details(api: Api) -> None:
    tab = api.new_intake()
    tab.run({**FI_SELF_BOOK})
    tab.post("/review/edit", {"turn": tab.view["turn"], "field_id": "gender"})
    view = tab.reply({"kind": "talk_to_person"})
    assert view["info"] == [
        "We have asked a staff member to contact you.",
        "They will use the phone number or email in your form.",
        "This is a demo. No one will contact you.",
        *t.NEEDS_HUMAN,
    ]


def test_review_lists_answers_by_section_and_what_is_missing(api: Api) -> None:
    tab = api.new_intake()
    tab.run({k: v for k, v in FI_SELF_BOOK.items() if k != "date_of_birth"})
    review = tab.get("/review").json()["review"]
    sections = {row["section"] for row in review["answered"]}
    assert {"Getting started", "About you", "Contact details"} <= sections
    assert [m["field_id"] for m in review["missing"]] == ["date_of_birth"]


def test_submit_incomplete_is_409_with_missing_list(api: Api) -> None:
    tab = api.new_intake()
    tab.run({"intake_type": "family_inquiry", "relationship": "me"})
    body = tab.turn("/submit", expect=409)
    assert body["code"] == "form_incomplete"
    assert body["view"]["state"] == "review"
    assert "full_name" in [m["field_id"] for m in body["view"]["review"]["missing"]]


def test_review_edit_pins_the_question(api: Api) -> None:
    tab = api.new_intake()
    tab.run(FI_SELF_BOOK)
    view = tab.post("/review/edit", {"turn": tab.view["turn"], "field_id": "phone"})
    assert view["question"]["field_id"] == "phone"


def test_autocomplete_hint_is_in_the_turn(api: Api) -> None:
    tab = api.new_intake()
    tab.turn("/start")
    tab.choose("family_inquiry")
    tab.choose("child")
    assert tab.view["question"]["field_id"] == "respondent_name"
    assert tab.view["question"]["autocomplete"] == "name"  # the person typing
    tab.text("Jordan Rivera")
    assert tab.view["question"]["field_id"] == "full_name"
    assert tab.view["question"]["autocomplete"] == "off"  # the child's name: never autofilled
