"""Fixed text that promises a human action is followed by the demo line while SYNTHETIC_ONLY.

This demo has no staff. Anything that says someone "will contact / call / email" the user
must be followed by "This is a demo. No one will contact you." wherever it is shown.
"""

import re
from collections.abc import Iterator
from pathlib import Path
from types import MappingProxyType

from app.api.errors import MESSAGES
from app.config import load_region_content
from app.domain import templates as t
from app.domain.registry import FIELDS
from app.services.email import BODY, body_lines
from app.workflow import commands as c
from app.workflow.understanding import ReplyKind
from tests.workflow_helpers import Driver, make_service, understood

PROMISE = re.compile(
    r"\bwill\b[^.]*\b(contact|call|email)\b|\basked a staff member\b", re.IGNORECASE
)
REGION = load_region_content("US")


def _strings(value: object) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, (tuple, list)):
        for item in value:
            yield from _strings(item)
    elif isinstance(value, (dict, MappingProxyType)):
        for item in value.values():
            yield from _strings(item)


def all_fixed_texts() -> set[str]:
    texts = set(_strings([v for k, v in vars(t).items() if k.isupper()]))
    for fld in FIELDS:
        texts |= {fld.question_self, fld.question_other, fld.why, fld.help}
        texts |= {o.label for o in fld.options}
    texts |= {REGION.crisis.heading, *REGION.crisis.lines}
    needs_human = REGION.needs_human
    texts |= {*needs_human.with_contact, *needs_human.without_contact, *needs_human.no_form}
    return texts | set(BODY) | set(MESSAGES.values())


def _promises(lines: list[str] | tuple[str, ...]) -> list[str]:
    return [line for line in lines if line != t.DEMO_NO_CONTACT and PROMISE.search(line)]


def test_every_fixed_promise_of_a_human_action_is_known() -> None:
    """A new promise cannot slip in: it must be added here and shown with the demo line."""
    assert set(_promises(sorted(all_fixed_texts()))) == {
        *REGION.needs_human.with_contact,
        REGION.needs_human.without_contact[0],
        "A staff member will read it and contact you.",
        CONTACT_WHY,
    }


CONTACT_WHY = "We will use the way you choose to contact you."


def test_why_text_that_promises_contact_shows_the_demo_line(tmp_path: Path) -> None:
    d = Driver(make_service(tmp_path / "intake.db"))
    d.send(c.Start())
    d.choose("family_inquiry")
    d.choose("me")
    d.text("Alex Rivera")
    d.text("May 4, 2004")
    q = d.view.question
    assert q is not None
    assert q.field_id == "preferred_contact_method"
    assert q.why == f"{CONTACT_WHY} {t.DEMO_NO_CONTACT}"
    view = d.text("why?", understood(ReplyKind.CLARIFICATION, clarification="why"))
    _assert_demo_line_follows_promises(list(view.info))


def _assert_demo_line_follows_promises(lines: list[str] | tuple[str, ...]) -> None:
    promises = _promises(lines)
    assert promises, lines
    assert t.DEMO_NO_CONTACT in lines
    last_promise = max(lines.index(p) for p in promises)
    demo = lines.index(t.DEMO_NO_CONTACT)
    assert last_promise < demo <= last_promise + 2  # right after the real-clinic lines


def _talk_to_person(tmp_path: Path, contact: bool) -> list[str]:
    d = Driver(make_service(tmp_path / "intake.db"))
    d.send(c.Start())
    d.choose("family_inquiry")
    d.choose("me")
    if contact:
        d.run(
            {
                "full_name": "Alex Rivera",
                "date_of_birth": "May 4, 2004",
                "preferred_contact_method": "email",
                "email": "alex@example.com",
            }
        )
        d.send(c.EditField(field_id="gender"))
    return list(d.send(c.TalkToPerson()).info)


def test_talk_to_a_person_shows_the_demo_line(tmp_path: Path) -> None:
    _assert_demo_line_follows_promises(_talk_to_person(tmp_path / "a", contact=False))
    _assert_demo_line_follows_promises(_talk_to_person(tmp_path / "b", contact=True))


def test_crisis_response_shows_the_demo_line(tmp_path: Path) -> None:
    d = Driver(make_service(tmp_path / "intake.db"))
    d.send(c.Start())
    d.choose("family_inquiry")
    d.choose("me")
    view = d.text("I want to kill myself")
    assert view.state.value == "needs_human"
    _assert_demo_line_follows_promises(list(view.info))


def test_email_body_shows_the_demo_line() -> None:
    _assert_demo_line_follows_promises(body_lines(synthetic=True))
    assert t.DEMO_NO_CONTACT not in body_lines(synthetic=False)


def test_crisis_response_says_each_thing_once(tmp_path: Path) -> None:
    d = Driver(make_service(tmp_path / "intake.db"))
    d.send(c.Start())
    d.choose("family_inquiry")
    d.choose("me")
    info = list(d.text("I want to kill myself").info)
    assert sum("Your answers are saved" in line for line in info) == 1
    assert info[-1] == "You can keep going on your own and add one."
