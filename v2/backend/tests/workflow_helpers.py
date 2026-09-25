"""Fakes and drivers for workflow tests. No network, no LLM, no API key."""

from collections import deque
from datetime import date
from pathlib import Path
from uuid import UUID

from app.config import Settings, load_region_content
from app.domain.types import IntakeType
from app.services.intake_service import IntakeService, TurnResult
from app.services.persistence import IntakeRepository, create_db_engine
from app.workflow import commands as c
from app.workflow.engine import Applied, EngineConfig, handle
from app.workflow.snapshot import EventRecord, Snapshot
from app.workflow.understanding import (
    FieldProposal,
    ReplyKind,
    ReplyUnderstanding,
    UnderstandingContext,
)
from app.workflow.view import TurnView, render

TODAY = date(2026, 9, 26)
FI, PR = IntakeType.FAMILY_INQUIRY.value, IntakeType.PROVIDER_REFERRAL.value

FI_SELF_BOOK: dict[str, str] = {
    "intake_type": FI,
    "relationship": "me",
    "full_name": "Alex Rivera",
    "date_of_birth": "May 4, 2004",
    "preferred_contact_method": "email",
    "email": "alex@example.com",
    "inquiry_reason": "autism_assessment",
    "phone": "202-555-0100",
    "address": "12 Oak Street, Springfield, IL 62701",
    "preferred_name": "Alex",
    "gender": "non_binary",
}
FI_CHILD_BOOK: dict[str, str] = {
    **FI_SELF_BOOK,
    "relationship": "child",
    "respondent_name": "Jordan Rivera",
    "email": "jordan@example.com",
}
PR_BOOK: dict[str, str] = {
    "intake_type": PR,
    "full_name": "Sam Park",
    "date_of_birth": "2001-02-03",
    "phone": "(202) 555-0143",
    "referral_provider_name": "Dr. Lee Moss",
    "referral_type": "specialist",
    "referral_date": "September 1, 2026",
    "email": "sam@example.com",
    "address": "4 Elm Road, Springfield, IL 62702",
    "referral_mode": "fax",
    "preferred_name": "Sam",
    "gender": "man",
}


def understood(
    kind: ReplyKind,
    *proposals: tuple[str, str] | tuple[str, str, str] | FieldProposal,
    **extra: str,
) -> ReplyUnderstanding:
    """Build an agent result, e.g. understood(ANSWER, ("full_name", "Alex Rivera"))."""
    props = []
    for p in proposals:
        if isinstance(p, FieldProposal):
            props.append(p)
        else:
            field_id, raw, *rest = p
            source = rest[0] if rest else "explicit"
            props.append(FieldProposal(field_id=field_id, raw_text=raw, value=raw, source=source))
    return ReplyUnderstanding(kind=kind, proposals=tuple(props), **extra)


class FakeUnderstander:
    """Answers the pending question with the message itself, unless a result is queued."""

    def __init__(self) -> None:
        self.queued: deque[ReplyUnderstanding] = deque()
        self.calls: list[tuple[str, UnderstandingContext]] = []

    def understand(self, message: str, context: UnderstandingContext) -> ReplyUnderstanding:
        self.calls.append((message, context))
        if self.queued:
            return self.queued.popleft()
        if context.pending is None:
            return ReplyUnderstanding(kind=ReplyKind.OFF_TOPIC)
        return understood(ReplyKind.ANSWER, (context.pending.id, message))


def make_service(db_path: Path, fake: FakeUnderstander | None = None) -> IntakeService:
    settings = Settings(database_url=f"sqlite:///{db_path.as_posix()}")
    repo = IntakeRepository(create_db_engine(settings.database_url))
    return IntakeService(repo, fake or FakeUnderstander(), settings, today=lambda: TODAY)


class Driver:
    """Plays one browser tab: always sends the turn number it last saw."""

    def __init__(self, service: IntakeService, intake_id: UUID | None = None) -> None:
        self.service = service
        if intake_id is None:
            created = service.create()
            self.id, self.token = created.intake_id, created.token
            self.view = created.view
        else:
            self.id, self.token = intake_id, ""
            view = service.view(intake_id)
            assert view is not None
            self.view = view

    @property
    def fake(self) -> FakeUnderstander:
        fake = self.service._understander  # test-only access
        assert isinstance(fake, FakeUnderstander)
        return fake

    def send(self, command: c.Command, *, expect: str = "applied") -> TurnView:
        result: TurnResult = self.service.handle(self.id, self.view.turn, command)
        assert result.status == expect, (result.status, result.reason, command)
        assert result.view is not None
        self.view = result.view
        return self.view

    def refresh(self) -> TurnView:
        view = self.service.view(self.id)
        assert view is not None
        self.view = view
        return view

    def text(self, message: str, u: ReplyUnderstanding | None = None, **kw: str) -> TurnView:
        if u is not None:
            self.fake.queued.append(u)
        return self.send(c.Text(text=message), **kw)

    def choose(self, option_id: str, extra: str | None = None) -> TurnView:
        return self.send(c.Choose(option_id=option_id, extra_text=extra))

    def answer(self, value: str) -> TurnView:
        q = self.view.question
        assert q is not None
        if q.input_type.value == "choice" and q.kind == "field":
            return self.choose(value)
        return self.text(value)

    def run(self, book: dict[str, str], stop_at_review: bool = True) -> TurnView:
        """Answer every field question from the book; skip anything not in it."""
        if self.view.state.value == "greeting":
            self.send(c.Start())
        for _ in range(60):
            q = self.view.question
            if q is None:
                break
            if q.kind != "field":
                self.choose("yes" if q.kind.startswith("confirm") else q.options[0].id)
            elif q.field_id in book:
                self.answer(book[q.field_id])
            else:
                self.send(c.Skip())
        if stop_at_review:
            assert self.view.state.value == "review", self.view.state
        return self.view

    def events(self) -> list[EventRecord]:
        return self.service._repo.events(self.id)  # test-only access

    def question_count(self, field_id: str) -> int:
        return sum(
            1
            for e in self.events()
            if e.type == "question_shown"
            and e.field_id == field_id
            and e.payload["kind"] == "field"
        )


class EngineHarness:
    """The pure engine without a database, for fast property tests."""

    def __init__(self, snap: Snapshot) -> None:
        self.snap = snap
        self.events: list[EventRecord] = []
        self.view = render(snap)
        self.config = EngineConfig(
            today=TODAY, region="US", max_field_attempts=3, crisis=load_region_content("US").crisis
        )

    def send(self, command: c.Command, u: ReplyUnderstanding | None = None) -> bool:
        result = handle(self.snap, command, self.config, u)
        if not isinstance(result, Applied):
            self.view = render(self.snap, result.notes)
            return False
        self.snap = result.snapshot
        self.events += result.events
        self.view = render(self.snap, result.notes)
        return True


def question_marks(view: TurnView) -> int:
    texts = [view.acknowledgement or "", *view.info, view.question.text if view.question else ""]
    return sum(text.count("?") for text in texts)
