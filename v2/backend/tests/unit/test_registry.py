import pytest

from app.domain.fields import FieldDef
from app.domain.parsing import Parsed, parse_answer
from app.domain.registry import BY_ID, FIELDS, SECTION_NAMES
from app.domain.types import InputType, NotSure
from tests.domain_helpers import REGION, TODAY


def test_ids_and_orders_are_unique() -> None:
    assert len({f.id for f in FIELDS}) == len(FIELDS)
    assert len({f.order for f in FIELDS}) == len(FIELDS)


def test_conditions_reference_real_fields_that_come_earlier() -> None:
    for field in FIELDS:
        for condition in field.conditions:
            assert condition.field_id in BY_ID
            assert BY_ID[condition.field_id].order < field.order


def test_sections_have_names() -> None:
    assert {f.section for f in FIELDS} <= set(SECTION_NAMES)


def test_option_ids_are_unique_per_field() -> None:
    for field in FIELDS:
        ids = [o.id for o in field.options]
        assert len(ids) == len(set(ids)), field.id


def test_only_intake_type_clarifies_on_not_sure() -> None:
    assert [f.id for f in FIELDS if f.not_sure is NotSure.CLARIFY] == ["intake_type"]


@pytest.mark.parametrize("field", [f for f in FIELDS if f.example], ids=lambda f: f.id)
def test_every_example_parses_with_its_own_field(field: FieldDef) -> None:
    assert field.example is not None
    assert isinstance(parse_answer(field, field.example, today=TODAY, region=REGION), Parsed)


def test_free_text_fields_have_an_example() -> None:
    free_text = [f for f in FIELDS if f.input_type is not InputType.CHOICE]
    assert all(f.example for f in free_text)


def test_choice_field_without_not_sure_is_rejected() -> None:
    with pytest.raises(ValueError, match="I'm not sure"):
        FieldDef.model_validate(
            {
                **BY_ID["referral_type"].model_dump(),
                "options": [o for o in BY_ID["referral_type"].options if o.special is None],
            }
        )
