"""Every fixed sentence the system shows, apart from field questions (registry.py) and
crisis text (content/regions/*.toml). Plain, literal, no blame, no exclamation marks.

Placeholders use str.format. All text here is checked by tests/unit/test_wording.py.
"""

from types import MappingProxyType

# --- Validation retries: shown before the same question again. Never "invalid" or "wrong".
RETRY: MappingProxyType[str, str] = MappingProxyType(
    {
        "date_unreadable": "I could not read that as a date.",
        "date_needs_full_year": "I need the full year, with four numbers.",
        "date_not_on_calendar": "I could not find that date on the calendar.",
        "date_in_future": "That date is after today.",
        "date_too_long_ago": "That date is a very long time ago.",
        "phone_unreadable": "I could not read that as a phone number.",
        "email_unreadable": "I could not read that as an email address.",
        "text_needs_letters": "I could not find any letters in that.",
        "text_too_long": "That is longer than I can save here.",
        "address_too_short": "I need more of the address.",
        "choose_option": "Please choose one of the buttons.",
        "type_a_few_words": "Please type a few words in the box.",
    }
)
RETRY_EXAMPLE = "Here is an example: {example}."

# --- Acknowledgements (never a question).
SAVED = "Saved."
NOT_SURE_OK = "That is okay."
SKIPPED = "Skipped."
ANSWER_LATER = "You can answer this later."
UPDATED = "Updated: {short_label} is {value}."
UNDONE = "Changed back: {short_label} is {value}."

# --- Single questions built from fixed parts. Exactly one "?" each.
CONFIRM_VALUE = "{label}: {value}. Is that right?"
DATE_CHOICE = "Which date do you mean?"
CONFLICT_EARLIER = "Earlier you said {old}."
CONFLICT_NOW = "Now you said {new}."
CONFLICT_QUESTION = "Which one is correct?"

# --- Start, pause, resume.
START = (
    "This form has about {total} questions.",
    "I will ask one question at a time.",
    "You can stop at any time. Your answers are saved as you go.",
)
PAUSED = (
    "Your answers are saved.",
    "To come back, open this page again or use this code.",
    "Write this code down.",
)
WELCOME_BACK = "Welcome back."
WELCOME_BACK_NAME = "Welcome back, {name}."

# --- Other reply kinds (docs/V2_SPEC.md §6.4).
OFF_TOPIC = "I can only help with this form."
UNSAFE = "I can only use the information for this form. I cannot send or share anything else."
NOT_UNDERSTOOD = "I did not understand. Here is the question again."
MESSAGE_TOO_LONG = "That message is too long for me to read. You can send a shorter one."
OVERWHELMED = (
    "This can feel like a lot. That is okay.",
    "You can take a break. Your answers are saved.",
    "You can also ask to talk to a person.",
)
MANY_TRIES = "We can come back to this question later."
NEEDS_HUMAN = "We have asked a staff member to contact you."

# --- Review screen.
REVIEW_STILL_NEEDED = "Still needed"
REVIEW_NOT_KNOWN = "Not known"
REVIEW_CANNOT_SUBMIT = "Some answers are still needed before you can send this form."
# Shown when a field is listed because its tier changed after it was skipped or not known.
NEEDED_BECAUSE_METHOD = "Needed because you chose {choice}."
NEEDED_FOR_CONTACT = "Needed so we have a way to contact you."

# --- Button labels.
BUTTONS: MappingProxyType[str, str] = MappingProxyType(
    {
        "start": "Start",
        "resume": "Go back to my form",
        "yes": "Yes",
        "no": "No",
        "neither": "Neither",
        "not_sure": "I'm not sure",
        "undo": "Undo",
        "skip": "Skip",
        "answer_later": "Answer later",
        "answer_now": "Answer now",
        "mark_unknown": "I don't know this",
        "why": "Why are you asking this?",
        "take_a_break": "Take a break",
        "talk_to_a_person": "Talk to a person",
        "keep_going": "Keep going",
        "continue_alone": "Continue on my own",
        "submit": "Send my form",
    }
)
