"""Plain-language checks on every fixed text (docs/V2_SPEC.md §3.1).

Questions: Flesch-Kincaid grade <= 6, <= 15 words, exactly one "?".
All sentences: grade <= 6, no "!", no blame words, no indirect requests.
"""

import re

import pytest
import textstat

from app.config import load_region_content
from app.domain import templates as t
from app.domain.clinical import CONDITION_CLAIMS
from app.domain.registry import FIELDS, get_field

MAX_GRADE = 6.0
MAX_QUESTION_WORDS = 15
MAX_LABEL_WORDS = 10

BANNED = re.compile(
    r"\b(invalid|wrong|error|mistake|incorrect|failed|must|hurry|quick(ly)?|asap|"
    r"could you|would you|can you|just|simply|obviously|oops)\b|!",
    re.IGNORECASE,
)

SAMPLE = {
    "example": "May 4, 2004",
    "short_label": "date of birth",
    "label": "your date of birth",
    "value": "May 4, 2004",
    "old": "May 4, 2004",
    "new": "June 4, 2004",
    "total": "12",
    "code": "ABCD 1234",
    "name": "Alex",
}

METHOD_OPTIONS = get_field("preferred_contact_method").options

QUESTIONS = sorted({q for f in FIELDS for q in (f.question_self, f.question_other)})

SENTENCES = [
    *(s for f in FIELDS for s in (f.why, f.help)),
    *t.RETRY.values(),
    t.RETRY_EXAMPLE,
    t.SAVED,
    t.NOT_SURE_OK,
    t.SKIPPED,
    t.UPDATED,
    t.UNDONE,
    t.CONFLICT_EARLIER,
    t.CONFLICT_NOW,
    *t.START,
    *t.PAUSED,
    t.WELCOME_BACK,
    t.WELCOME_BACK_NAME,
    t.OFF_TOPIC,
    t.UNSAFE,
    t.NOT_UNDERSTOOD,
    t.MESSAGE_TOO_LONG,
    *t.OVERWHELMED,
    t.MANY_TRIES,
    t.NEEDS_HUMAN,
    t.REVIEW_CANNOT_SUBMIT,
    t.NEEDED_FOR_CONTACT,
    *(t.NEEDED_BECAUSE_METHOD.format(choice=o.label) for o in METHOD_OPTIONS),
    load_region_content("US").crisis.heading,
    *load_region_content("US").crisis.lines,
]

COMPOSED_QUESTIONS = [
    *(t.CONFIRM_VALUE.format(label=f.label_self, value="Sample value") for f in FIELDS),
    *(t.CONFIRM_VALUE.format(label=f.label_other, value="Sample value") for f in FIELDS),
    " ".join([t.CONFLICT_EARLIER, t.CONFLICT_NOW, t.CONFLICT_QUESTION]).format(**SAMPLE),
    t.DATE_CHOICE,
]

LABELS = [
    *(o.label for f in FIELDS for o in f.options),
    *t.BUTTONS.values(),
    t.REVIEW_STILL_NEEDED,
    t.REVIEW_NOT_KNOWN,
]


def _grade(text: str) -> float:
    return float(textstat.flesch_kincaid_grade(text.format(**SAMPLE)))


@pytest.mark.parametrize("question", QUESTIONS)
def test_question_templates_are_plain(question: str) -> None:
    assert question.count("?") == 1
    assert question.endswith("?")
    assert len(question.split()) <= MAX_QUESTION_WORDS
    assert _grade(question) <= MAX_GRADE
    assert not BANNED.search(question)


@pytest.mark.parametrize("question", COMPOSED_QUESTIONS)
def test_composed_questions_have_exactly_one_question(question: str) -> None:
    assert question.count("?") == 1
    assert not BANNED.search(question)


@pytest.mark.parametrize("sentence", SENTENCES)
def test_fixed_sentences_are_plain(sentence: str) -> None:
    assert "?" not in sentence
    assert _grade(sentence) <= MAX_GRADE
    assert not BANNED.search(sentence)


@pytest.mark.parametrize("label", LABELS)
def test_labels_are_short_and_calm(label: str) -> None:
    assert len(label.split()) <= MAX_LABEL_WORDS
    assert "!" not in label


@pytest.mark.parametrize("text", QUESTIONS + SENTENCES + LABELS)
def test_no_fixed_text_claims_a_condition(text: str) -> None:
    assert not CONDITION_CLAIMS.search(text)
