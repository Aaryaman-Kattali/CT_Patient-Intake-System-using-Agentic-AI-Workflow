"""Request and response bodies. The frontend generates its TypeScript types from these.

Every conversational endpoint answers with a `TurnView` (docs/V2_SPEC.md §9.2): at most one
question, never a list. Every error answers with an `ErrorBody`. Request bodies forbid
unknown fields, so for example a recipient can never be smuggled into the email request.
"""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.workflow import commands as c
from app.workflow.view import ActionView, TurnView


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TurnRequest(_Body):
    turn: int = Field(ge=0, description="The turn number the client last saw.")


ReplyCommand = Annotated[
    c.Choose | c.Text | c.Skip | c.Undo | c.KeepGoing | c.TalkToPerson | c.MarkUnknown,
    Field(discriminator="kind"),
]


class ReplyRequest(TurnRequest):
    command: ReplyCommand


class EditRequest(TurnRequest):
    field_id: str = Field(max_length=64)


class ResumeCodeRequest(_Body):
    resume_code: str = Field(max_length=32)


class EmailRequest(_Body):
    """Empty on purpose: there is no recipient. It comes from the stored email field."""


class SessionView(BaseModel):
    """A new intake, or one opened on a new device with a resume code."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    token: str
    view: TurnView


ErrorCode = Literal[
    "invalid_request",
    "intake_not_found",
    "not_found",
    "method_not_allowed",
    "stale_turn",
    "action_not_available",
    "form_incomplete",
    "idempotency_key_required",
    "email_not_submitted",
    "email_no_address",
    "email_not_synthetic",
    "email_failed",
    "not_submitted",
    "resume_failed",
    "too_many_attempts",
    "internal_error",
]


class ErrorBody(BaseModel):
    """Every error: a fixed code and a fixed message. Never exception text or field values."""

    model_config = ConfigDict(frozen=True)

    code: ErrorCode
    message: str
    view: TurnView | None = None  # the current turn, where it helps (e.g. stale_turn)
    actions: tuple[ActionView, ...] = ()  # e.g. "Talk to a person" when locked out


class HelpView(BaseModel):
    """Fixed text for "Talk to a person" when no form is open (e.g. locked out)."""

    model_config = ConfigDict(frozen=True)

    info: tuple[str, ...]


class ResumeCodeView(BaseModel):
    """The resume code, on request from the "Take a break" area."""

    model_config = ConfigDict(frozen=True)

    resume_code: str
    info: tuple[str, ...]


class UiText(BaseModel):
    """Every fixed word the frontend shows besides questions and answers (principle P3)."""

    model_config = ConfigDict(frozen=True)

    buttons: dict[str, str]
    labels: dict[str, str]
    sentences: dict[str, str]  # may contain {placeholders}, filled in by the frontend
