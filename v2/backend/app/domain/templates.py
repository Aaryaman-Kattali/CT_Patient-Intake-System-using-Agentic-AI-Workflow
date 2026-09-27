"""Every fixed sentence the system shows, apart from field questions (registry.py) and
crisis text (content/regions/*.toml). Plain, literal, no blame, no exclamation marks.

Placeholders use str.format. All text here is checked by tests/unit/test_wording.py.
"""

import re
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
# The code on request, from the Take a break area (any time after starting).
RESUME_CODE_INFO = (
    "With this code you can come back to your form on any device.",
    "Write this code down.",
)
WELCOME_BACK = "Welcome back."
WELCOME_BACK_NAME = "Welcome back, {name}."

# --- Other reply kinds (docs/V2_SPEC.md §6.4).
OFF_TOPIC = "I can only help with this form."
UNSAFE = "I can only use the information for this form. I cannot send or share anything else."
# The model worked but found nothing usable in the reply.
NOT_UNDERSTOOD = "I did not understand. Here is the question again."
# The model could not be used (no key, timeout, error, unreadable output). Not the user's
# mistake. The first version is for questions with buttons, the second for typed answers.
LLM_UNAVAILABLE_BUTTONS = (
    "Typing is not working right now.",
    "You can use the buttons, or take a break and come back.",
)
LLM_UNAVAILABLE_TYPED = (
    "Typing is not working right now.",
    "Please try again in a moment, or take a break and come back.",
)
MESSAGE_TOO_LONG = "That message is too long for me to read. You can send a shorter one."
OVERWHELMED = (
    "This can feel like a lot. That is okay.",
    "You can take a break. Your answers are saved.",
    "You can also ask to talk to a person.",
)
EMAIL_SENT = "We sent an email to say we have your form."
MANY_TRIES = "We can come back to this question later."
# "Talk to a person": the real-clinic lines come from the region file; these follow them.
NEEDS_HUMAN = ("Your answers are saved.", "You can keep going on your own at any time.")
NEEDS_HUMAN_NO_CONTACT = ("Your answers are saved.", "You can keep going on your own and add one.")
# Shown right after any fixed text that promises a human action, while SYNTHETIC_ONLY.
DEMO_NO_CONTACT = "This is a demo. No one will contact you."
HUMAN_PROMISE = re.compile(
    r"\bwill\b[^.]*\b(contact|call|email)\b|\basked a staff member\b", re.IGNORECASE
)


def promises_contact(text: str) -> bool:
    return text != DEMO_NO_CONTACT and HUMAN_PROMISE.search(text) is not None


def with_demo_notice(text: str, synthetic: bool) -> str:
    """One string (e.g. a field's `why`): the demo line is added after a promise of contact."""
    return f"{text} {DEMO_NO_CONTACT}" if synthetic and promises_contact(text) else text


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


# --- Text the frontend shows around the questions (served by GET /ui/text). The frontend
# writes no wording of its own: every word a user sees comes from this module or the registry.
UI_LABELS: MappingProxyType[str, str] = MappingProxyType(
    {
        "send": "Send",
        "answer_box": "Your answer",
        "text_size": "Text size",
        "text_bigger": "Bigger text",
        "text_smaller": "Smaller text",
        "your_code": "Your code",
        "copy_code": "Copy code",
        "show_code": "Show my code",
        "have_code": "I have a code",
        "enter_code": "Type your code",
        "review_title": "Check your answers",
        "your_answers": "Your answers",
        "change": "Change",
        "email_me": "Email me a confirmation",
        "staff_view": "Staff view (demo)",
        "new_form": "Start a new form",
        "back": "Back",
        "progress": "Your progress",
        "done": "Done",
        "still_needed": REVIEW_STILL_NEEDED,
    }
)
UI_SENTENCES: MappingProxyType[str, str] = MappingProxyType(
    {
        "reading": "Reading your answer…",
        "example": "Example: {example}",
        "progress": "Question {number} of about {total}",
        "code_copied": "The code is copied.",
        "no_connection": "The form cannot be reached right now. Please try again in a moment.",
        "resume_intro": "Type the code you wrote down. Then you can go on with your form.",
        # Staff page only (/staff/<intake id>). The patient pages never link to it.
        "staff_open_here": "Open this page in the browser where the form was filled in.",
    }
)
# After the form is sent (the engine adds no text of its own on submit).
SUBMITTED = ("Thank you. We have your form.", "You can close this page now.")
