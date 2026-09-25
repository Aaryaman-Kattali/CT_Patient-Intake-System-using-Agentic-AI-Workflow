"""Orchestrates one turn: load -> (understand) -> engine -> save, all or nothing."""

import hashlib
import hmac
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from uuid import UUID, uuid4

from app.config import Settings, load_region_content
from app.domain.registry import get_field
from app.domain.requirements import applicable_fields
from app.services.persistence import IntakeRepository
from app.services.resume_codes import lookup_hash, resume_code_for
from app.workflow import commands as c
from app.workflow.engine import (
    Applied,
    EngineConfig,
    FieldQuestion,
    Notes,
    QueueQuestion,
    current_question,
    handle,
    needs_understanding,
)
from app.workflow.snapshot import EventRecord, Snapshot
from app.workflow.states import State
from app.workflow.understanding import (
    FieldBrief,
    ReplyKind,
    ReplyUnderstanding,
    Understander,
    UnderstandingContext,
)
from app.workflow.view import TurnView, render


def hash_secret(secret: str) -> str:
    """For the 256-bit demo session token (not an auth system; see README)."""
    return hashlib.sha256(secret.encode()).hexdigest()


@dataclass(frozen=True)
class Created:
    intake_id: UUID
    token: str
    view: TurnView


@dataclass(frozen=True)
class TurnResult:
    status: str  # "applied" | "stale" | "rejected" | "not_found"
    view: TurnView | None
    reason: str | None = None


class IntakeService:
    def __init__(
        self,
        repo: IntakeRepository,
        understander: Understander,
        settings: Settings,
        today: Callable[[], date] = date.today,
    ) -> None:
        self._repo = repo
        self._understander = understander
        self._settings = settings
        self._today = today

    def _config(self) -> EngineConfig:
        return EngineConfig(
            today=self._today(),
            region=self._settings.region,
            max_field_attempts=self._settings.max_field_attempts,
            crisis=load_region_content(self._settings.region).crisis,
        )

    def create(self) -> Created:
        token = secrets.token_urlsafe(32)
        snap = Snapshot(id=uuid4(), state=State.GREETING)
        self._repo.create(snap, hash_secret(token), (EventRecord(type="created"),))
        return Created(intake_id=snap.id, token=token, view=render(snap))

    def verify_token(self, intake_id: UUID, token: str) -> bool:
        stored = self._repo.token_hash(intake_id)
        return stored is not None and hmac.compare_digest(stored, hash_secret(token))

    def find_by_resume_code(self, code: str) -> UUID | None:
        code_hash = lookup_hash(code, self._secret)
        return self._repo.find_by_resume_code_hash(code_hash) if code_hash else None

    def resume_code(self, intake_id: UUID) -> str:
        return resume_code_for(intake_id, self._secret)

    def view(self, intake_id: UUID) -> TurnView | None:
        snap = self._repo.load(intake_id)
        return self._render(snap) if snap else None

    def _render(self, snap: Snapshot, notes: Notes | None = None) -> TurnView:
        code = self.resume_code(snap.id) if snap.state is State.PAUSED else None
        return render(snap, notes, resume_code=code)

    @property
    def _secret(self) -> bytes:
        return self._settings.app_secret.get_secret_value().encode()

    def handle(self, intake_id: UUID, expected_turn: int, command: c.Command) -> TurnResult:
        snap = self._repo.load(intake_id)
        if snap is None:
            return TurnResult("not_found", None)
        if snap.turn != expected_turn:  # stale tab or double click: change nothing
            return TurnResult("stale", self._render(snap), "stale_turn")
        understanding: ReplyUnderstanding | None = None
        if isinstance(command, c.Text) and needs_understanding(snap, command.text):
            understanding = self._understander.understand(command.text, _context(snap))
            if understanding.kind is ReplyKind.PAUSE:
                command = c.Pause()
        if isinstance(command, c.Pause):
            code_hash = lookup_hash(self.resume_code(snap.id), self._secret) or ""
            command = c.Pause(resume_code_hash=code_hash)
        result = handle(snap, command, self._config(), understanding)
        if not isinstance(result, Applied):
            return TurnResult("rejected", self._render(snap, result.notes), result.reason)
        if not self._repo.save(result.snapshot, expected_turn, result.events):
            current = self._repo.load(intake_id)
            return TurnResult("stale", self._render(current) if current else None, "stale_turn")
        return TurnResult("applied", self._render(result.snapshot, result.notes))


def _brief(field_id: str) -> FieldBrief:
    fld = get_field(field_id)
    return FieldBrief(
        id=fld.id,
        description=fld.short_label,
        input_type=fld.input_type,
        option_ids=tuple(o.id for o in fld.options),
    )


def _context(snap: Snapshot) -> UnderstandingContext:
    """What the agent may see: field ids and types, never stored values (spec §6.2)."""
    q = current_question(snap)
    pending: FieldBrief | None = None
    if isinstance(q, FieldQuestion):
        pending = _brief(q.field.id)
    elif isinstance(q, QueueQuestion):
        pending = _brief(q.item.field_id)
    return UnderstandingContext(
        pending=pending,
        applicable=tuple(_brief(f.id) for f in applicable_fields(snap.answers)),
        answered_field_ids=tuple(k for k, v in snap.answers.items() if v.answered),
    )
