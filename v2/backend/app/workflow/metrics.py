"""Metrics computed from the event log. Shared by tests and the eval harness."""

from collections.abc import Iterable

from app.workflow.snapshot import EventRecord

# Events after which a field counts as resolved (it has a saved status).
_RESOLVING = frozenset(
    {
        "field_accepted",
        "field_confirmed",
        "field_corrected",
        "field_skipped",
        "field_deferred",
        "field_dont_know",
        "field_marked_unknown",
    }
)
# Events after which a field has no saved status again.
_UNRESOLVING = frozenset({"field_cleared"})


def repeated_questions(events: Iterable[EventRecord]) -> int:
    """Field questions shown again after the field was resolved, without the user asking.

    Not counted: re-showing an unresolved question (clarification, off-topic, retry), and
    questions the user re-opened themselves (review edit, "Neither" on a conflict: pinned).
    """
    resolved: set[str] = set()
    repeats = 0
    for e in events:
        if e.field_id is None:
            continue
        if e.type in _RESOLVING:
            resolved.add(e.field_id)
        elif e.type in _UNRESOLVING or (
            e.type == "correction_undone" and not e.payload.get("restored")
        ):
            resolved.discard(e.field_id)
        elif _is_unrequested_field_question(e) and e.field_id in resolved:
            repeats += 1
    return repeats


def _is_unrequested_field_question(e: EventRecord) -> bool:
    return (
        e.type == "question_shown"
        and e.payload.get("kind") == "field"
        and not e.payload.get("pinned")
    )
