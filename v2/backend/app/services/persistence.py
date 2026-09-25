"""SQLite persistence via SQLModel. Column types are chosen to port to Postgres unchanged.

- Every turn is saved in ONE transaction, guarded by the turn number (optimistic lock):
  a stale or duplicate reply cannot save twice or skip a question.
- intake_events is append-only. This module has no update or delete path for it, and
  SQLite triggers refuse UPDATE/DELETE as a second line of defence.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, Column, DateTime, Engine, UniqueConstraint, event, func, text
from sqlalchemy.engine import make_url
from sqlmodel import Field, Session, SQLModel, create_engine, delete, select, update

from app.domain.fields import FieldState
from app.domain.types import FieldStatus, Source
from app.workflow.snapshot import EventRecord, PendingItem, Snapshot, UndoRecord
from app.workflow.states import State
from app.workflow.understanding import LlmCallInfo


def _now() -> datetime:
    return datetime.now(UTC)


def _ts() -> Any:
    return Field(default_factory=_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class IntakeRow(SQLModel, table=True):
    __tablename__ = "intakes"

    id: UUID = Field(primary_key=True)
    state: str
    turn: int = 0
    resume_state: str | None = None
    pinned_field: str | None = None
    return_to_review: bool = False
    interruption: str | None = None
    attempts: dict[str, int] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    undo: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    token_hash: str
    resume_code_hash: str | None = Field(default=None, index=True)
    synthetic: bool = True
    created_at: datetime = _ts()
    updated_at: datetime = _ts()


class FieldValueRow(SQLModel, table=True):
    __tablename__ = "field_values"
    __table_args__ = (UniqueConstraint("intake_id", "field_id"),)

    id: int | None = Field(default=None, primary_key=True)
    intake_id: UUID = Field(foreign_key="intakes.id", index=True)
    field_id: str
    status: str
    value: str | None = None
    display: str | None = None
    extra_text: str | None = None
    source: str | None = None
    unresolved_other: str | None = None
    updated_at: datetime = _ts()


class PendingItemRow(SQLModel, table=True):
    __tablename__ = "pending_items"
    __table_args__ = (UniqueConstraint("intake_id", "seq"),)

    id: int | None = Field(default=None, primary_key=True)
    intake_id: UUID = Field(foreign_key="intakes.id", index=True)
    seq: int
    payload: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))


class EventRow(SQLModel, table=True):
    __tablename__ = "intake_events"
    __table_args__ = (UniqueConstraint("intake_id", "seq"),)

    id: int | None = Field(default=None, primary_key=True)
    intake_id: UUID = Field(foreign_key="intakes.id", index=True)
    seq: int
    turn: int
    type: str
    field_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = _ts()


class LlmCallRow(SQLModel, table=True):
    """Model, tokens, latency and reply kind per call. Never prompt or response text."""

    __tablename__ = "llm_calls"

    id: int | None = Field(default=None, primary_key=True)
    intake_id: UUID = Field(foreign_key="intakes.id", index=True)
    agent: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int
    status: str
    attempts: int = 1
    reply_kind: str | None = None
    created_at: datetime = _ts()


_APPEND_ONLY_TRIGGERS = (
    """CREATE TRIGGER IF NOT EXISTS intake_events_no_update BEFORE UPDATE ON intake_events
       BEGIN SELECT RAISE(ABORT, 'intake_events is append-only'); END""",
    """CREATE TRIGGER IF NOT EXISTS intake_events_no_delete BEFORE DELETE ON intake_events
       BEGIN SELECT RAISE(ABORT, 'intake_events is append-only'); END""",
)


def create_db_engine(database_url: str) -> Engine:
    """Create the engine and tables. One engine per app instance; no module globals."""
    url = make_url(database_url)
    if url.get_backend_name() == "sqlite" and url.database:
        Path(url.database).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(database_url)
    if url.get_backend_name() == "sqlite":
        event.listen(engine, "connect", _sqlite_pragmas)
    SQLModel.metadata.create_all(engine)
    if url.get_backend_name() == "sqlite":
        with engine.begin() as conn:
            for statement in _APPEND_ONLY_TRIGGERS:
                conn.execute(text(statement))
    return engine


def _sqlite_pragmas(dbapi_connection: Any, _record: Any) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


class IntakeRepository:
    """The only way the app reads or writes intakes. Events can only be appended."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def create(self, snap: Snapshot, token_hash: str, events: tuple[EventRecord, ...]) -> None:
        with Session(self._engine) as session, session.begin():
            session.add(IntakeRow(**_intake_columns(snap), token_hash=token_hash))
            session.flush()
            self._append(session, snap.id, snap.turn, events)

    def load(self, intake_id: UUID) -> Snapshot | None:
        with Session(self._engine) as session:
            row = session.get(IntakeRow, intake_id)
            if row is None:
                return None
            values = session.exec(select(FieldValueRow).where(FieldValueRow.intake_id == intake_id))
            pending = session.exec(
                select(PendingItemRow)
                .where(PendingItemRow.intake_id == intake_id)
                .order_by(PendingItemRow.seq)  # type: ignore[arg-type]
            )
            return Snapshot(
                id=row.id,
                state=State(row.state),
                turn=row.turn,
                resume_state=State(row.resume_state) if row.resume_state else None,
                answers={v.field_id: _field_state(v) for v in values},
                queue=tuple(PendingItem.model_validate(p.payload) for p in pending),
                pinned_field=row.pinned_field,
                return_to_review=row.return_to_review,
                interruption="overwhelmed" if row.interruption == "overwhelmed" else None,
                attempts=dict(row.attempts),
                undo=UndoRecord.model_validate(row.undo) if row.undo else None,
                resume_code_hash=row.resume_code_hash,
            )

    def save(self, snap: Snapshot, expected_turn: int, events: tuple[EventRecord, ...]) -> bool:
        """Save a new snapshot only if nobody else saved since `expected_turn`.

        Returns False (and writes nothing) for a stale or duplicate reply.
        """
        with Session(self._engine) as session, session.begin():
            result = session.exec(
                update(IntakeRow)
                .where(IntakeRow.id == snap.id, IntakeRow.turn == expected_turn)  # type: ignore[arg-type]
                .values(**_intake_columns(snap), updated_at=_now())
            )
            if result.rowcount != 1:
                return False
            self._write_answers(session, snap)
            self._write_queue(session, snap)
            self._append(session, snap.id, snap.turn, events)
            return True

    def events(self, intake_id: UUID) -> list[EventRecord]:
        with Session(self._engine) as session:
            rows = session.exec(
                select(EventRow).where(EventRow.intake_id == intake_id).order_by(EventRow.seq)  # type: ignore[arg-type]
            )
            return [EventRecord(type=r.type, field_id=r.field_id, payload=r.payload) for r in rows]

    def record_llm_call(
        self, intake_id: UUID, agent: str, call: LlmCallInfo, reply_kind: str | None
    ) -> None:
        with Session(self._engine) as session, session.begin():
            session.add(
                LlmCallRow(
                    intake_id=intake_id,
                    agent=agent,
                    reply_kind=reply_kind,
                    **call.model_dump(),
                )
            )

    def llm_calls(self, intake_id: UUID) -> list[LlmCallRow]:
        with Session(self._engine) as session:
            rows = session.exec(select(LlmCallRow).where(LlmCallRow.intake_id == intake_id))
            return list(rows)

    def token_hash(self, intake_id: UUID) -> str | None:
        with Session(self._engine) as session:
            row = session.get(IntakeRow, intake_id)
            return row.token_hash if row else None

    def find_by_resume_code_hash(self, code_hash: str) -> UUID | None:
        with Session(self._engine) as session:
            row = session.exec(
                select(IntakeRow).where(IntakeRow.resume_code_hash == code_hash)
            ).first()
            return row.id if row else None

    # --- private helpers (events: append only) ---------------------------------

    @staticmethod
    def _append(
        session: Session, intake_id: UUID, turn: int, events: tuple[EventRecord, ...]
    ) -> None:
        last = session.exec(
            select(func.max(EventRow.seq)).where(EventRow.intake_id == intake_id)
        ).one()
        seq = last or 0
        for e in events:
            seq += 1
            session.add(
                EventRow(
                    intake_id=intake_id,
                    seq=seq,
                    turn=turn,
                    type=e.type,
                    field_id=e.field_id,
                    payload=e.payload,
                )
            )

    @staticmethod
    def _write_answers(session: Session, snap: Snapshot) -> None:
        existing = {
            r.field_id: r
            for r in session.exec(select(FieldValueRow).where(FieldValueRow.intake_id == snap.id))
        }
        for field_id, row in existing.items():
            if field_id not in snap.answers:
                session.delete(row)
        for field_id, state in snap.answers.items():
            row = existing.get(field_id) or FieldValueRow(
                intake_id=snap.id, field_id=field_id, status=state.status.value
            )
            row.status = state.status.value
            row.value, row.display, row.extra_text = state.value, state.display, state.extra_text
            row.source = state.source.value if state.source else None
            row.unresolved_other = state.unresolved_other
            row.updated_at = _now()
            session.add(row)

    @staticmethod
    def _write_queue(session: Session, snap: Snapshot) -> None:
        session.exec(delete(PendingItemRow).where(PendingItemRow.intake_id == snap.id))  # type: ignore[arg-type]
        for seq, item in enumerate(snap.queue):
            session.add(
                PendingItemRow(intake_id=snap.id, seq=seq, payload=item.model_dump(mode="json"))
            )


def _intake_columns(snap: Snapshot) -> dict[str, Any]:
    return {
        "id": snap.id,
        "state": snap.state.value,
        "turn": snap.turn,
        "resume_state": snap.resume_state.value if snap.resume_state else None,
        "pinned_field": snap.pinned_field,
        "return_to_review": snap.return_to_review,
        "interruption": snap.interruption,
        "attempts": dict(snap.attempts),
        "undo": snap.undo.model_dump(mode="json") if snap.undo else None,
        "resume_code_hash": snap.resume_code_hash,
    }


def _field_state(row: FieldValueRow) -> FieldState:
    return FieldState(
        status=FieldStatus(row.status),
        value=row.value,
        display=row.display,
        extra_text=row.extra_text,
        source=Source(row.source) if row.source else None,
        unresolved_other=row.unresolved_other,
    )
