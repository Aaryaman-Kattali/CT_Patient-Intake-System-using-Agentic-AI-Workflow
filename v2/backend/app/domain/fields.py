"""Field definition models. The registry of actual fields lives in registry.py."""

from collections.abc import Mapping
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, model_validator

from app.domain.types import ANSWERED, FieldStatus, InputType, IntakeType, NotSure, Source, Tier

NOT_SURE_ID = "not_sure"
PREFER_NOT_ID = "prefer_not"


class Option(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    label: str
    special: Literal["not_sure", "prefer_not"] | None = None
    free_text: bool = False  # shows a text box on the same screen


class Condition(BaseModel):
    """Holds when the referenced field's current value matches. All conditions must hold."""

    model_config = ConfigDict(frozen=True)

    field_id: str
    equals: str | None = None
    not_equals: str | None = None  # also holds when the field has no value yet

    def holds(self, answers: "Answers") -> bool:
        value = answer_value(answers, self.field_id)
        if self.equals is not None:
            return value == self.equals
        if self.not_equals is not None:
            return value != self.not_equals
        return True


class FieldDef(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    section: str
    order: int
    tier: Tier
    input_type: InputType
    question_self: str
    question_other: str
    label_self: str
    label_other: str
    short_label: str
    why: str
    help: str
    example: str | None = None
    options: tuple[Option, ...] = ()
    conditions: tuple[Condition, ...] = ()
    about_respondent_in: frozenset[IntakeType] = frozenset()
    not_sure: NotSure = NotSure.DEFER
    single_wording: bool = False  # same question for everyone (e.g. referral fields)

    @model_validator(mode="after")
    def _choice_fields_have_options(self) -> Self:
        if (self.input_type is InputType.CHOICE) != bool(self.options):
            raise ValueError(f"{self.id}: options are required for choice fields and only them")
        if self.options and not any(o.special == "not_sure" for o in self.options):
            raise ValueError(f"{self.id}: choice fields must offer 'I'm not sure'")
        if self.single_wording and self.question_self != self.question_other:
            raise ValueError(f"{self.id}: single_wording fields need identical questions")
        return self

    def option(self, option_id: str) -> Option | None:
        return next((o for o in self.options if o.id == option_id), None)


class FieldState(BaseModel):
    """The current saved state of one field for one intake."""

    model_config = ConfigDict(frozen=True)

    status: FieldStatus
    value: str | None = None
    display: str | None = None  # how the value is shown back ("May 4, 2004")
    extra_text: str | None = None  # typed text for a free_text option
    source: Source | None = None

    @property
    def answered(self) -> bool:
        return self.status in ANSWERED


Answers = Mapping[str, FieldState]


def answer_value(answers: Answers, field_id: str) -> str | None:
    state = answers.get(field_id)
    return state.value if state is not None and state.answered else None
