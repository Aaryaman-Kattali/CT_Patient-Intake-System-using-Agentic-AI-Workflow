"""Small builders for domain tests. No I/O, no LLM."""

from datetime import date

from app.domain.fields import FieldState
from app.domain.requirements import next_field
from app.domain.types import FieldStatus

TODAY = date(2026, 9, 26)
REGION = "US"

Script = dict[str, str | FieldStatus]


def state(value: str | FieldStatus) -> FieldState:
    if isinstance(value, FieldStatus):
        return FieldState(status=value)
    return FieldState(status=FieldStatus.ACCEPTED, value=value)


def build(**values: str | FieldStatus) -> dict[str, FieldState]:
    return {field_id: state(v) for field_id, v in values.items()}


def walk(script: Script, max_steps: int = 40) -> tuple[list[str], dict[str, FieldState]]:
    """Ask questions in engine order, answering each from the script.

    Fields missing from the script are skipped (optional) or deferred (needed), which is
    what a user pressing Skip / Answer later would do. Returns the asked field ids.
    """
    from app.domain.requirements import is_needed

    answers: dict[str, FieldState] = {}
    asked: list[str] = []
    for _ in range(max_steps):
        field = next_field(answers)
        if field is None:
            return asked, answers
        asked.append(field.id)
        if field.id in script:
            answers[field.id] = state(script[field.id])
        elif is_needed(field, answers):
            answers[field.id] = state(FieldStatus.DEFERRED)
        else:
            answers[field.id] = state(FieldStatus.SKIPPED)
    raise AssertionError(f"walk did not finish: {asked}")
