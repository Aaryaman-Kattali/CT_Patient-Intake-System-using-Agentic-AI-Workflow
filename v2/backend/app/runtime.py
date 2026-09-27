"""Process checks at startup. The resume-code rate limits (and the 429 hedge cooldown) live in
memory, so the API must run as ONE process: one uvicorn worker."""

import logging
from collections.abc import Mapping, Sequence

log = logging.getLogger(__name__)

_WORKER_FLAGS = ("--workers", "-w")


def configured_workers(argv: Sequence[str], env: Mapping[str, str]) -> int:
    """Workers requested via --workers / -w (uvicorn, gunicorn) or WEB_CONCURRENCY. 1 if none."""
    counts = [_int(env.get("WEB_CONCURRENCY"))]
    for i, arg in enumerate(argv):
        flag, _, value = arg.partition("=")
        if flag in _WORKER_FLAGS:
            counts.append(_int(value or (argv[i + 1] if i + 1 < len(argv) else None)))
    return max([c for c in counts if c is not None] or [1])


def warn_if_multiple_workers(argv: Sequence[str], env: Mapping[str, str]) -> bool:
    workers = configured_workers(argv, env)
    if workers > 1:
        log.warning(
            "more than one worker configured; rate limits are in memory, run a single process",
            extra={"workers": workers},
        )
    return workers > 1


def _int(value: str | None) -> int | None:
    try:
        return int(value) if value else None
    except ValueError:
        return None
