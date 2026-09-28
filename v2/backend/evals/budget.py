"""Stay well inside the API key's limits (docs/V2_SPEC.md §14.4).

Every model request counts: first requests, hedges and retries. Before each turn that may call
the model, the runner waits until the requests (and tokens) of the last 60 seconds plus the
worst case for one turn fit under the limits. The daily count is saved on disk; when a turn
would pass the daily limit, the run stops cleanly and resumes the next day.

Owner's key (gemini-3.5-flash-lite): 15 RPM, 250k TPM, 500 RPD.
Limits used: 70 % of RPM and TPM, and 80 % of RPD.
"""

import json
import math
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

KEY_RPM, KEY_TPM, KEY_RPD = 15, 250_000, 500
EVAL_RPM = math.floor(KEY_RPM * 0.70)  # 10
EVAL_TPM = math.floor(KEY_TPM * 0.70)  # 175 000
EVAL_RPD = math.floor(KEY_RPD * 0.80)  # 400
WORST_REQUESTS_PER_TURN = 4  # first + hedge + one parse retry + one transient-error retry
WORST_TOKENS_PER_REQUEST = 3_000  # about 1 200 in practice; generous on purpose
QUOTA_DAY = ZoneInfo("America/Los_Angeles")  # Gemini daily quotas reset at midnight Pacific


def quota_file(runs: Path, profile: str, model: str) -> Path:
    """One daily counter per API project (a label, never the key) and model."""
    return runs / f"quota-{profile}-{model}.json"


class DailyLimitReached(Exception):
    """Stop cleanly: the next turn could pass today's request limit."""


@dataclass
class Limits:
    rpm: int = EVAL_RPM
    tpm: int = EVAL_TPM
    rpd: int = EVAL_RPD
    worst_requests: int = WORST_REQUESTS_PER_TURN
    tokens_per_request: int = WORST_TOKENS_PER_REQUEST  # worst-case estimate before a turn


# Per model: 70 % of RPM and TPM (as the owner set them), 80 % of RPD.
MODEL_LIMITS = {
    "gemini-3.5-flash-lite": Limits(),  # key: 15 RPM, 250K TPM, 500 RPD
    # key: 30 RPM, 16K TPM, 14.4K RPD. 20 RPM and 11K TPM, whichever is hit first.
    "gemma-4-26b-a4b-it": Limits(rpm=20, tpm=11_000, rpd=11_520, tokens_per_request=1_500),
}


class Budget:
    def __init__(
        self,
        state_file: Path,
        limits: Limits | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        today: Callable[[], str] | None = None,
    ) -> None:
        self.limits = limits or Limits()
        self._file = state_file
        self._clock, self._sleep = clock, sleep
        self._today = today or (lambda: datetime.now(QUOTA_DAY).date().isoformat())
        self._window: deque[tuple[float, int, int]] = deque()  # (time, requests, tokens)
        self.waited_s = 0.0

    # --- daily count, saved so a stopped run resumes with the right numbers ---------------

    def used_today(self) -> int:
        state = self._load()
        requests = state.get("requests")
        return requests if isinstance(requests, int) and state.get("day") == self._today() else 0

    def _load(self) -> dict[str, object]:
        try:
            loaded: dict[str, object] = json.loads(self._file.read_text(encoding="utf-8"))
            return loaded
        except (OSError, ValueError):
            return {}

    def _save_daily(self, requests: int) -> None:
        self._file.parent.mkdir(parents=True, exist_ok=True)
        state = {"day": self._today(), "requests": self.used_today() + requests}
        self._file.write_text(json.dumps(state), encoding="utf-8")

    # --- per-minute window --------------------------------------------------------------

    def _recent(self) -> tuple[int, int]:
        now = self._clock()
        while self._window and now - self._window[0][0] >= 60:
            self._window.popleft()
        return sum(r for _, r, _ in self._window), sum(t for _, _, t in self._window)

    def before_turn(self, worst: int | None = None) -> None:
        """Wait until one more worst-case turn fits; raise if it would pass today's limit.
        `worst`: requests this step can make at most (1 for a single model call)."""
        worst = self.limits.worst_requests if worst is None else worst
        if self.used_today() + worst > self.limits.rpd:
            raise DailyLimitReached(f"{self.used_today()} of {self.limits.rpd} used today")
        while True:
            requests, tokens = self._recent()
            if (
                requests + worst <= self.limits.rpm
                and tokens + worst * self.limits.tokens_per_request <= self.limits.tpm
            ):
                return
            oldest = self._window[0][0]
            pause = max(0.5, 60 - (self._clock() - oldest))
            self.waited_s += pause
            self._sleep(pause)

    def after_turn(self, requests: int, tokens: int) -> None:
        if requests <= 0:
            return
        self._window.append((self._clock(), requests, tokens))
        self._save_daily(requests)
