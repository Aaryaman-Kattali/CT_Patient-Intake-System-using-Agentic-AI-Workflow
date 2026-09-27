"""Hedged model calls (docs/V2_SPEC.md §6): one deadline per turn, a second identical request
when the first is slow, and a small retry budget. Plain asyncio; knows nothing about ADK.

- One overall deadline. Nothing runs past it.
- No reply after `hedge_after_s`: start one identical request. The first valid result wins
  and every other request is cancelled. A cancelled request's result is never used.
- Unreadable output: one more attempt, if time remains.
- Transient API error (429, 5xx): one retry after about 1 s (with jitter), if time remains.
  Any other error ends the call at once: an identical request would fail the same way.
- After a 429, no hedging for `cooldown_after_429_s`: a second request would only add load
  while the quota is exhausted. The call records that the hedge was suppressed.
"""

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal

Failure = Literal["parse_error", "error"]
Status = Literal["ok", "parse_error", "timeout", "error"]
Usage = tuple[int | None, int | None]

# Cancelled requests finish their clean-up in the background; keep them referenced until then.
_CANCELLED: set[asyncio.Task[Any]] = set()


@dataclass(frozen=True)
class AttemptResult[T]:
    value: T | None = None
    usage: Usage = (None, None)
    failure: Failure | None = None
    error_class: str | None = None
    transient: bool = False


@dataclass(frozen=True)
class HedgePolicy:
    deadline_s: float
    hedge_after_s: float
    retry_delay_s: float = 1.0
    cooldown_after_429_s: float = 60.0


class Cooldown:
    """Remembers the last 429 for this process (one understander per app)."""

    def __init__(self, seconds: float) -> None:
        self._seconds = seconds
        self._last: float | None = None

    def start(self) -> None:
        self._last = time.monotonic()

    def active(self) -> bool:
        return self._last is not None and time.monotonic() - self._last < self._seconds


@dataclass(frozen=True)
class HedgeOutcome[T]:
    value: T | None
    status: Status
    attempts: int
    hedged: bool
    winner: int | None = None  # 1 = first request, 2 = the next one started, ...
    hedge_suppressed: bool = False  # the hedge was due but skipped after a recent 429
    usage: Usage = (None, None)
    error_class: str | None = None


async def hedged_call[T](
    attempt: Callable[[], Awaitable[AttemptResult[T]]],
    policy: HedgePolicy,
    may_hedge: Callable[[], bool] = lambda: True,
) -> HedgeOutcome[T]:
    return await _Hedge(attempt, policy, may_hedge).run()


class _Hedge[T]:
    def __init__(
        self,
        attempt: Callable[[], Awaitable[AttemptResult[T]]],
        policy: HedgePolicy,
        may_hedge: Callable[[], bool],
    ) -> None:
        self._attempt = attempt
        self._policy = policy
        self._may_hedge = may_hedge
        self._loop = asyncio.get_running_loop()
        started = self._loop.time()
        self._deadline = started + policy.deadline_s
        self._hedge_at = started + policy.hedge_after_s
        self._tasks: dict[asyncio.Task[AttemptResult[T]], int] = {}
        self._attempts = 0
        self._hedge_due = self._hedged = self._suppressed = False
        self._retried_parse = self._retried_error = False
        self._last: AttemptResult[T] | None = None

    async def run(self) -> HedgeOutcome[T]:
        self._launch()
        try:
            return await self._wait_for_winner()
        finally:
            self._cancel_all()

    async def _wait_for_winner(self) -> HedgeOutcome[T]:
        while self._tasks:
            wake = self._deadline if self._hedge_due else min(self._hedge_at, self._deadline)
            done, _ = await asyncio.wait(
                self._tasks,
                timeout=max(0.0, wake - self._loop.time()),
                return_when=asyncio.FIRST_COMPLETED,
            )
            if not done:
                if self._loop.time() >= self._deadline:
                    return self._fail("timeout")
                self._hedge()
                continue
            for task in done:
                number = self._tasks.pop(task)
                result = task.result()
                if result.value is not None:
                    return self._win(result, number)
                self._last = result
                if result.failure == "error" and not result.transient:
                    return self._fail("error")
            if not self._tasks:
                self._retry()
        return self._fail(self._last.failure if self._last and self._last.failure else "error")

    def _hedge(self) -> None:
        self._hedge_due = True
        if self._may_hedge():
            self._hedged = True
            self._launch()
        else:
            self._suppressed = True

    def _retry(self) -> None:
        last = self._last
        remaining = self._deadline - self._loop.time()
        if last is None or remaining <= 0:
            return
        if last.failure == "parse_error" and not self._retried_parse:
            self._retried_parse = True
            self._launch()
        elif last.transient and not self._retried_error:
            delay = self._policy.retry_delay_s * random.uniform(1.0, 1.5)  # noqa: S311
            if delay < remaining:
                self._retried_error = True
                self._launch(delay)

    def _launch(self, delay: float = 0.0) -> None:
        self._attempts += 1
        self._tasks[asyncio.create_task(self._delayed(delay))] = self._attempts

    async def _delayed(self, delay: float) -> AttemptResult[T]:
        if delay:
            await asyncio.sleep(delay)
        return await self._attempt()

    def _cancel_all(self) -> None:
        for task in self._tasks:
            task.cancel()
            _CANCELLED.add(task)
            task.add_done_callback(_CANCELLED.discard)
        self._tasks.clear()

    def _win(self, result: AttemptResult[T], number: int) -> HedgeOutcome[T]:
        return HedgeOutcome(
            result.value,
            "ok",
            self._attempts,
            self._hedged,
            number,
            self._suppressed,
            result.usage,
        )

    def _fail(self, status: Status) -> HedgeOutcome[T]:
        last = self._last
        return HedgeOutcome(
            None,
            status,
            self._attempts,
            self._hedged,
            hedge_suppressed=self._suppressed,
            usage=last.usage if last else (None, None),
            error_class=last.error_class if last else None,
        )
