"""Chooses between the fixed self/other templates. Never builds new question text."""

from app.domain.fields import Answers, FieldDef, answer_value
from app.domain.registry import SECTION_NAMES
from app.domain.types import IntakeType


def intake_type_of(answers: Answers) -> IntakeType | None:
    value = answer_value(answers, "intake_type")
    return IntakeType(value) if value in set(IntakeType) else None


def respondent_is_patient(answers: Answers) -> bool:
    return (
        intake_type_of(answers) is IntakeType.FAMILY_INQUIRY
        and answer_value(answers, "relationship") == "me"
    )


def is_about_respondent(field: FieldDef, answers: Answers) -> bool:
    return intake_type_of(answers) in field.about_respondent_in


def uses_self_wording(field: FieldDef, answers: Answers) -> bool:
    return is_about_respondent(field, answers) or respondent_is_patient(answers)


def question_text(field: FieldDef, answers: Answers) -> str:
    return field.question_self if uses_self_wording(field, answers) else field.question_other


def field_label(field: FieldDef, answers: Answers) -> str:
    return field.label_self if uses_self_wording(field, answers) else field.label_other


def section_name(section: str, answers: Answers) -> str:
    self_name, other_name = SECTION_NAMES[section]
    return self_name if respondent_is_patient(answers) else other_name
