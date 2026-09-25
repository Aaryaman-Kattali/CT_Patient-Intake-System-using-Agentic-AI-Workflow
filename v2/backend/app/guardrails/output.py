"""Checks on the agent's proposal BEFORE the engine sees it (docs/V2_SPEC.md §10.2).

A proposal survives only if it names a real, applicable field and quotes text that really
appears in the user's message. Everything dropped is reported, never silently ignored.
"""

import re
from dataclasses import dataclass

from app.domain.normalizers import normalize_text
from app.workflow.understanding import (
    FieldProposal,
    ReplyKind,
    ReplyUnderstanding,
    UnderstandingContext,
)

MAX_PROPOSALS = 8
_KINDS_WITH_PROPOSALS = frozenset(
    {ReplyKind.ANSWER, ReplyKind.ANSWER_PLUS_EXTRA, ReplyKind.CORRECTION}
)


@dataclass(frozen=True)
class Checked:
    understanding: ReplyUnderstanding
    dropped: tuple[tuple[str, str], ...]  # (field_id, reason)


def _canon(text: str) -> str:
    return re.sub(r"\s+", " ", normalize_text(text)).casefold().strip()


def check(
    message: str,
    u: ReplyUnderstanding,
    context: UnderstandingContext,
    flags: frozenset[str] = frozenset(),
) -> Checked:
    if u.kind not in _KINDS_WITH_PROPOSALS:
        no_values = tuple((p.field_id, "kind_has_no_values") for p in u.proposals)
        return Checked(u.model_copy(update={"proposals": ()}), no_values)
    known = {f.id for f in context.applicable}
    pending = context.pending.id if context.pending else None
    haystack = _canon(message)
    kept: list[FieldProposal] = []
    dropped: list[tuple[str, str]] = []
    for p in u.proposals[:MAX_PROPOSALS]:
        reason = _reject_reason(p, known, pending, haystack, flags)
        if reason:
            dropped.append((p.field_id, reason))
        else:
            kept.append(p)
    dropped += [(p.field_id, "too_many_proposals") for p in u.proposals[MAX_PROPOSALS:]]
    return Checked(u.model_copy(update={"proposals": tuple(kept)}), tuple(dropped))


def _reject_reason(
    p: FieldProposal,
    known: set[str],
    pending: str | None,
    haystack: str,
    flags: frozenset[str],
) -> str | None:
    if p.field_id not in known:
        return "unknown_field"
    quote = _canon(p.raw_text)
    if not quote or quote not in haystack:
        return "quote_not_in_message"
    if p.field_id == "email" and pending != "email" and "send" in flags:
        return "email_with_send_request"  # "send this to x@..." must never become an answer
    return None
