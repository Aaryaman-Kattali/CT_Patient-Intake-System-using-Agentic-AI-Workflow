"""PII redaction for logs (docs/V2_SPEC.md §10.4).

A logging filter replaces every value known for the current intake (set per turn via a
context variable, including the raw message) and generic patterns (emails, phone numbers,
dates) with [REDACTED]. Logs should carry ids, field ids, states and event types only;
this filter is the safety net if a value slips into a log line anyway.
"""

import logging
import re
from contextvars import ContextVar

MASK = "[REDACTED]"
CURRENT_VALUES: ContextVar[frozenset[str]] = ContextVar("current_values", default=frozenset())

PATTERNS = (
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),  # emails
    re.compile(r"(?<!\w)\+?\d[\d\s().-]{7,}\d(?!\w)"),  # phone-like numbers
    re.compile(r"\b\d{1,4}[/.-]\d{1,2}[/.-]\d{1,4}\b"),  # numeric dates
    re.compile(
        r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{1,2}(st|nd|rd|th)?,?\s+\d{4}\b",
        re.IGNORECASE,
    ),  # "May 4, 2004"
)
_SAFE_KEYS = frozenset({"intake_id", "turn", "latency_ms"})


def add_values(values: set[str]) -> None:
    CURRENT_VALUES.set(CURRENT_VALUES.get() | frozenset(v for v in values if v))


def redact(text: str) -> str:
    for value in sorted(CURRENT_VALUES.get(), key=len, reverse=True):
        if len(value) >= 2:
            text = re.sub(re.escape(value), MASK, text, flags=re.IGNORECASE)
    for pattern in PATTERNS:
        text = pattern.sub(MASK, text)
    return text


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage())
        record.args = ()
        for key, value in list(vars(record).items()):
            if key not in _SAFE_KEYS and isinstance(value, str) and key not in ("msg", "name"):
                setattr(record, key, redact(value))
        if record.exc_info and record.exc_info[1] is not None:
            record.exc_text = redact(logging.Formatter().formatException(record.exc_info))
            record.exc_info = None
        return True
