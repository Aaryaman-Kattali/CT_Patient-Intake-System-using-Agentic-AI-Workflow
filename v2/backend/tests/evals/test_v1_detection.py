"""The V1 adapter's field detection (keyword rules on V1's free-text questions)."""

import pytest

from evals.v1_adapter import asked_fields, questions_in


@pytest.mark.parametrize(
    ("text", "fields"),
    [
        ("Are you here for Family Inquiry or Provider Referral services?", ["intake_type"]),
        ("Please provide the client's full name.", ["full_name"]),
        ("What is the client's date of birth (YYYY-MM-DD)?", ["date_of_birth"]),
        (
            "What is your preferred contact method? (Phone, Email, Mail, Text)",
            ["preferred_contact_method"],
        ),
        ("Could you provide the name of the referring provider?", ["referral_provider_name"]),
        ("What is the client's email address?", ["email"]),
        ("What is the client's gender and email address?", ["gender", "email"]),
        ("What is the client's home address?", ["address"]),
        ("Is all of this information correct?", []),
    ],
)
def test_detection(text: str, fields: list[str]) -> None:
    assert asked_fields(text) == fields


def test_questions_per_message_counts_fields_asked_together() -> None:
    assert questions_in("What is the client's gender and email address?") == 2
    assert questions_in("What is your name? And your date of birth?") == 2


@pytest.mark.parametrize(
    ("text", "fields"),
    [  # messages from the first V1 run that the first rules misread
        ("Would you like to transfer to the email agent now?", []),
        ("Finally, what are your contact details (phone/email/address)?", ["contact_details"]),
        (
            "Please provide the Contact Details (such as your phone number, email address, "
            "or mailing address where we can reach you):",
            ["contact_details"],
        ),
    ],
)
def test_detection_fixes_after_the_first_v1_run(text: str, fields: list[str]) -> None:
    assert asked_fields(text) == fields
