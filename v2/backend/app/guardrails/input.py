"""Checks on the user's message BEFORE any LLM call (docs/V2_SPEC.md §10.1).

- Too long: a fixed message, and the text is never sent to the LLM.
- Crisis words: the fixed crisis response, whatever the LLM would say (it is not called).
- Injection patterns: a flag for the output check. The real defence is structural: the agent
  has no tools and can only propose field values that the application re-checks.
"""

import re
from dataclasses import dataclass, field

from app.domain.normalizers import normalize_text

INJECTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (name, re.compile(pattern, re.IGNORECASE))
    for name, pattern in (
        ("override", r"\b(ignore|disregard|forget)\b.{0,40}\b(instruction|rule|prompt)s?\b"),
        ("role", r"\b(you are now|act as|pretend to be|developer mode|jailbreak)\b"),
        ("system", r"\b(system prompt|system message|hidden prompt)\b"),
        ("send", r"\b(send|forward|email|mail|share)\b.{0,60}\b(to|with)\b"),
        (
            "records",
            r"\b(other|another|all|every)\b.{0,20}\b(patients?|records?|clients?|forms?)\b",
        ),
        ("list", r"\b(list|show|dump|export)\b.{0,20}\b(all|every|database|records?)\b"),
    )
)


@dataclass(frozen=True)
class Screened:
    text: str
    too_long: bool = False
    crisis: bool = False
    flags: frozenset[str] = field(default_factory=frozenset)


def screen(raw: str, *, max_chars: int, crisis_keywords: tuple[str, ...]) -> Screened:
    text = normalize_text(raw)
    if len(text) > max_chars:
        return Screened(text="", too_long=True)
    lowered = text.casefold()
    crisis = any(keyword.casefold() in lowered for keyword in crisis_keywords)
    flags = frozenset(name for name, pattern in INJECTION_PATTERNS if pattern.search(text))
    return Screened(text=text, crisis=crisis, flags=flags)
