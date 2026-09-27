"""Counts failed attempts per key in a sliding window (resume codes, docs/V2_SPEC.md §8).

In memory, per process: enough for this single-process demo. Once a key has
`max_failures` failures inside `window_s`, it is blocked until the oldest one expires.
"""

import time
from collections import deque
from collections.abc import Callable

# Resume-code lockouts last 15 minutes. The fixed lockout message says so.
RESUME_WINDOW_S = 15 * 60


class FailureLimiter:
    def __init__(
        self, max_failures: int, window_s: float, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._max = max_failures
        self._window = window_s
        self._clock = clock
        self._failures: dict[str, deque[float]] = {}

    def blocked(self, key: str) -> bool:
        return self._count(key) >= self._max

    def record_failure(self, key: str) -> None:
        self._count(key)
        self._failures.setdefault(key, deque()).append(self._clock())

    def _count(self, key: str) -> int:
        """Failures inside the window. Keys with none left are dropped, so memory stays small."""
        stamps = self._failures.get(key)
        if stamps is None:
            return 0
        now = self._clock()
        while stamps and now - stamps[0] >= self._window:
            stamps.popleft()
        if not stamps:
            del self._failures[key]
        return len(stamps)
