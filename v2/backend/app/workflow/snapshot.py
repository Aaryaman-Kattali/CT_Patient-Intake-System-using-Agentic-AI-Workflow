"""The full state of one intake, as the engine sees it. Persistence maps this to rows."""

from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.fields import FieldState
from app.domain.types import Source
from app.workflow.states import State


class PendingKind(StrEnum):
    CONFIRM_EXTRA = "confirm_extra"  # an extra value from a reply: yes / no
    CONFIRM_VALUE = "confirm_value"  # inferred or single-reading value for the asked field
    CONFLICT = "conflict"  # a new value differs from a saved one
    DATE_CHOICE = "date_choice"  # 04/05/2004: April 5 or May 4


class Choice(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: str
    display: str


class PendingItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: PendingKind
    field_id: str
    value: str | None = None
    display: str | None = None
    extra_text: str | None = None
    source: Source = Source.EXPLICIT
    choices: tuple[Choice, ...] = ()  # DATE_CHOICE
    old_display: str | None = None  # CONFLICT


class UndoRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    field_id: str
    previous: FieldState | None
    valid_for_turn: int  # only the turn right after the correction


class EventRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: str
    field_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class Snapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    state: State
    turn: int = 0
    resume_state: State | None = None
    answers: dict[str, FieldState] = Field(default_factory=dict)
    queue: tuple[PendingItem, ...] = ()
    pinned_field: str | None = None
    return_to_review: bool = False
    interruption: Literal["overwhelmed"] | None = None
    attempts: dict[str, int] = Field(default_factory=dict)
    undo: UndoRecord | None = None
    resume_code_hash: str | None = None
