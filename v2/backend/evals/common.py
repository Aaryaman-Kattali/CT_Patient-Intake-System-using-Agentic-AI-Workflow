"""Helpers shared by the V2 runner, the metrics and the V1 adapter (no app imports here:
the V1 adapter runs in V1's own environment)."""

import re
import sys


def norm(value: str | None) -> str:
    """Exact match after normalization: case, spaces and punctuation do not count."""
    return re.sub(r"\s+", " ", re.sub(r"[^\w@.+ ]", " ", (value or "").casefold())).strip()


def say(*parts: object) -> None:
    """Progress for the person running the eval (a CLI, so stdout, not the log)."""
    sys.stdout.write(" ".join(str(p) for p in parts) + "\n")
    sys.stdout.flush()
