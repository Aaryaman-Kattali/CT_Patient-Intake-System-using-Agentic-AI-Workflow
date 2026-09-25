"""Core enums shared by the domain, workflow and persistence layers."""

from enum import StrEnum


class IntakeType(StrEnum):
    FAMILY_INQUIRY = "family_inquiry"
    PROVIDER_REFERRAL = "provider_referral"


class InputType(StrEnum):
    TEXT = "text"
    DATE = "date"
    CHOICE = "choice"
    PHONE = "phone"
    EMAIL = "email"


class Tier(StrEnum):
    """How strongly a field is needed. `conditional` is resolved per path (see requirements.py)."""

    MUST_HAVE = "must_have"
    REQUIRED = "required"
    OPTIONAL = "optional"
    CONDITIONAL = "conditional"


class NotSure(StrEnum):
    """What "I'm not sure" means while a field is effectively must_have/required.

    On an effectively optional field it is always final (status dont_know).
    """

    CLARIFY = "clarify"  # show fixed help text + the same buttons again
    ANSWER = "answer"  # a complete answer staff can follow up on
    DEFER = "defer"  # status deferred, shown on review


class FieldStatus(StrEnum):
    ACCEPTED = "accepted"
    CONFIRMED = "confirmed"
    SKIPPED = "skipped"
    DEFERRED = "deferred"
    DONT_KNOW = "dont_know"
    UNKNOWN_CONFIRMED = "unknown_confirmed"


class Source(StrEnum):
    """Provenance of a value. Inferred values always need a yes/no confirmation."""

    EXPLICIT = "explicit"  # quoted from the user's message
    INFERRED = "inferred"  # the LLM mapped the user's words to a value
    BUTTON = "button"
    REVIEW_EDIT = "review_edit"


ANSWERED = frozenset({FieldStatus.ACCEPTED, FieldStatus.CONFIRMED})
