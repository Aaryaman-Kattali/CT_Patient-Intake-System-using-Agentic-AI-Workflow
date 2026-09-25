"""The contract between the workflow and the understanding agent (docs/V2_SPEC.md §6).

The agent only proposes. The engine decides what, if anything, changes.
"""

from enum import StrEnum
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict

from app.domain.types import InputType


class ReplyKind(StrEnum):
    ANSWER = "answer"
    ANSWER_PLUS_EXTRA = "answer_plus_extra"
    CORRECTION = "correction"
    CLARIFICATION = "clarification"
    DONT_KNOW = "dont_know"
    SKIP = "skip"
    PAUSE = "pause"
    OFF_TOPIC = "off_topic"
    DISTRESS = "distress"
    UNSAFE = "unsafe"


class FieldProposal(BaseModel):
    model_config = ConfigDict(frozen=True)

    field_id: str
    raw_text: str  # exact span from the user's message
    value: str  # the agent's reading; the stored value is re-derived from raw_text
    source: Literal["explicit", "inferred"]


class ReplyUnderstanding(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: ReplyKind
    proposals: tuple[FieldProposal, ...] = ()
    clarification: Literal["why", "meaning"] | None = None
    distress_level: Literal["overwhelmed", "crisis"] | None = None


class FieldBrief(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    description: str
    input_type: InputType
    option_ids: tuple[str, ...] = ()


class UnderstandingContext(BaseModel):
    """Everything the agent sees besides the message. No stored values (spec §6.2)."""

    model_config = ConfigDict(frozen=True)

    pending: FieldBrief | None
    applicable: tuple[FieldBrief, ...]
    answered_field_ids: tuple[str, ...]


class Understander(Protocol):
    def understand(self, message: str, context: UnderstandingContext) -> ReplyUnderstanding: ...
