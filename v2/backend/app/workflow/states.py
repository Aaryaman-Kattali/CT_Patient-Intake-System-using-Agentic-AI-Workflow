from enum import StrEnum


class State(StrEnum):
    GREETING = "greeting"
    CHOOSE_INTAKE_TYPE = "choose_intake_type"
    COLLECTING = "collecting"
    CONFIRMING_EXTRA = "confirming_extra"
    RESOLVING_CONFLICT = "resolving_conflict"
    REVIEW = "review"
    SUBMITTED = "submitted"
    PAUSED = "paused"
    NEEDS_HUMAN = "needs_human"


COLLECTING_STATES = frozenset(
    {
        State.CHOOSE_INTAKE_TYPE,
        State.COLLECTING,
        State.CONFIRMING_EXTRA,
        State.RESOLVING_CONFLICT,
        State.REVIEW,
    }
)
