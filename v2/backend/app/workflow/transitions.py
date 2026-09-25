"""Every allowed state change, in one table (docs/V2_SPEC.md §7.2).

The engine computes a target state; `check` refuses any (from, trigger, to) not listed here.
`allowed` tells the engine whether a command may run in the current state at all.
"""

from enum import StrEnum
from types import MappingProxyType

from app.workflow.states import COLLECTING_STATES, State

S = State


class Trigger(StrEnum):
    START = "start"
    ANSWER = "answer"  # a reply that saves, queues, or resolves something
    INFO = "info"  # clarification, off-topic, retry, distress text: no state change
    EDIT_FIELD = "edit_field"
    MARK_UNKNOWN = "mark_unknown"
    SUBMIT = "submit"
    PAUSE = "pause"
    RESUME = "resume"
    NEEDS_HUMAN = "needs_human"
    CONTINUE_ALONE = "continue_alone"
    UNDO = "undo"


_ASKING = frozenset({S.CHOOSE_INTAKE_TYPE, S.COLLECTING, S.CONFIRMING_EXTRA, S.RESOLVING_CONFLICT})

TABLE: MappingProxyType[tuple[State, Trigger], frozenset[State]] = MappingProxyType(
    {
        (S.GREETING, Trigger.START): frozenset({S.CHOOSE_INTAKE_TYPE}),
        (S.CHOOSE_INTAKE_TYPE, Trigger.ANSWER): frozenset(
            {S.CHOOSE_INTAKE_TYPE, S.COLLECTING, S.CONFIRMING_EXTRA}
        ),
        (S.COLLECTING, Trigger.ANSWER): frozenset(
            {S.COLLECTING, S.CONFIRMING_EXTRA, S.RESOLVING_CONFLICT, S.REVIEW}
        ),
        (S.CONFIRMING_EXTRA, Trigger.ANSWER): frozenset(
            {S.CHOOSE_INTAKE_TYPE, S.COLLECTING, S.CONFIRMING_EXTRA, S.RESOLVING_CONFLICT, S.REVIEW}
        ),
        (S.RESOLVING_CONFLICT, Trigger.ANSWER): frozenset(
            {S.COLLECTING, S.CONFIRMING_EXTRA, S.RESOLVING_CONFLICT, S.REVIEW}
        ),
        **{(s, Trigger.INFO): frozenset({s}) for s in COLLECTING_STATES},
        (S.REVIEW, Trigger.EDIT_FIELD): frozenset({S.CHOOSE_INTAKE_TYPE, S.COLLECTING}),
        (S.REVIEW, Trigger.MARK_UNKNOWN): frozenset({S.REVIEW}),
        (S.REVIEW, Trigger.SUBMIT): frozenset({S.SUBMITTED, S.REVIEW}),
        **{(s, Trigger.PAUSE): frozenset({S.PAUSED}) for s in COLLECTING_STATES},
        (S.PAUSED, Trigger.RESUME): COLLECTING_STATES,
        **{(s, Trigger.NEEDS_HUMAN): frozenset({S.NEEDS_HUMAN}) for s in COLLECTING_STATES},
        (S.NEEDS_HUMAN, Trigger.CONTINUE_ALONE): COLLECTING_STATES,
        **{(s, Trigger.UNDO): COLLECTING_STATES for s in _ASKING | {S.REVIEW}},
    }
)


class IllegalTransition(RuntimeError):
    pass


def allowed(state: State, trigger: Trigger) -> bool:
    return (state, trigger) in TABLE


def check(state: State, trigger: Trigger, target: State) -> None:
    if target not in TABLE.get((state, trigger), frozenset()):
        raise IllegalTransition(f"{state} --{trigger}--> {target} is not in the transition table")
