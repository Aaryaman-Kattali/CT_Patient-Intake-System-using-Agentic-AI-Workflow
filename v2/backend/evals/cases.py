"""Eval cases (docs/V2_SPEC.md §14.1). Synthetic only; scripted, never an LLM-simulated user.

A case is a persona (a communication pattern) with an answer book, a few special turns, and
the expected outcome. The runner answers whichever question is asked from the book, so a case
does not break when the question order changes. Everything is deterministic and repeatable.
"""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DATASET = Path(__file__).parent / "datasets" / "v2_cases.jsonl"


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Answer(_Model):
    """How the persona answers one field. Choice fields are buttons, as in the real UI."""

    say: str | None = None  # typed text (text, date, phone and email fields)
    press: str | None = None  # an option id (choice fields)
    extra_text: str | None = None  # the text box of a free-text option
    skip: bool = False  # the Skip / Answer later button
    kinds: tuple[str, ...] = ("answer",)  # reply kinds that count as correctly understood
    retry: str | None = None  # typed again if the first answer could not be read


class Special(_Model):
    """A special turn, used once, the first time `at` is the question being asked."""

    at: str
    say: str | None = None
    action: Literal["pause", "talk_to_person"] | None = None
    kinds: tuple[str, ...] = ()  # expected reply kinds (empty for deterministic turns)
    must_show: tuple[str, ...] = ()  # fixed texts that must appear in the reply
    then: Literal["keep_going", "continue_alone"] | None = None  # the button pressed next
    forbidden: tuple[str, ...] = ()  # injected values that must never be saved


class Expected(_Model):
    status: str  # accepted | confirmed | skipped | deferred | dont_know | unknown_confirmed
    value: str | None = None  # canonical (ISO date, E.164 phone, option id, text)
    unresolved_other: str | None = None


class Case(_Model):
    id: str
    category: str
    persona: str
    intake: Literal["fi_self", "fi_other", "pr"]
    book: dict[str, Answer]
    specials: tuple[Special, ...] = ()
    expected: dict[str, Expected]
    conflict_choice: dict[str, Literal["old", "new", "not_sure"]] = Field(default_factory=dict)
    mark_unknown: tuple[str, ...] = ()  # "I don't know this" on the review screen
    max_confirmations: int = 0  # yes/no and date questions the case legitimately needs
    inferred_ok: tuple[str, ...] = ()  # fields where a yes/no on the asked field is fine
    complete: bool = True  # the script intends to send the form


def load_cases(path: Path = DATASET) -> list[Case]:
    with path.open(encoding="utf-8") as f:
        return [Case.model_validate(json.loads(line)) for line in f if line.strip()]
