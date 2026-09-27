"""A scripted model that plugs into the real ADK LlmAgent + Runner. No network, no key."""

import asyncio
import json
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any

from google.adk.models import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import errors, types
from pydantic import PrivateAttr

from app.agents.hedging import HedgePolicy
from app.agents.understanding_agent import AdkUnderstander

RAISE = "__raise__"  # a non-API error (e.g. a dropped connection): never retried


@dataclass(frozen=True)
class Slow:
    """Answer only after `seconds` (a slow API)."""

    seconds: float
    reply: str | dict[str, Any] = "{}"


SLEEP = Slow(5.0)  # slower than any test deadline


@dataclass(frozen=True)
class ApiError:
    """Fail like the Gemini API does, with this HTTP status code."""

    code: int


Script = str | dict[str, Any] | Slow | ApiError


class ScriptedLlm(BaseLlm):
    """Replies in order: request n gets the n-th script entry. Records which requests ran to
    the end, so tests can check that a cancelled request never produced a result."""

    model: str = "scripted-test-model"
    _replies: list[Script] = PrivateAttr(default_factory=list)
    _requests: list[LlmRequest] = PrivateAttr(default_factory=list)
    _finished: list[int] = PrivateAttr(default_factory=list)

    def reply_with(self, *replies: Script) -> "ScriptedLlm":
        self._replies.extend(replies)
        return self

    @property
    def requests(self) -> list[LlmRequest]:
        return self._requests

    @property
    def finished(self) -> list[int]:
        return self._finished

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        self._requests.append(llm_request)
        number = len(self._requests)
        entry = self._replies.pop(0) if self._replies else "{}"
        if isinstance(entry, Slow):
            await asyncio.sleep(entry.seconds)
            entry = entry.reply
        if isinstance(entry, ApiError):
            error = errors.ServerError if entry.code >= 500 else errors.ClientError
            raise error(entry.code, {"error": {"code": entry.code, "message": "simulated"}})
        if entry == RAISE:
            raise ConnectionError("simulated connection error")
        self._finished.append(number)
        text = entry if isinstance(entry, str) else json.dumps(entry)
        yield LlmResponse(
            content=types.Content(role="model", parts=[types.Part(text=text)]),
            usage_metadata=types.GenerateContentResponseUsageMetadata(
                prompt_token_count=120, candidates_token_count=30
            ),
        )


def make_understander(
    llm: BaseLlm,
    *,
    deadline_s: float = 30.0,  # generous: the first ADK call in a cold CI process can be slow
    hedge_after_s: float | None = None,  # None: never hedge
    retry_delay_s: float = 0.01,
    cooldown_after_429_s: float = 60.0,
) -> AdkUnderstander:
    policy = HedgePolicy(
        deadline_s=deadline_s,
        hedge_after_s=deadline_s if hedge_after_s is None else hedge_after_s,
        retry_delay_s=retry_delay_s,
        cooldown_after_429_s=cooldown_after_429_s,
    )
    return AdkUnderstander(llm, policy)


def request_text(request: LlmRequest) -> str:
    """Everything the model was sent: system instruction plus contents."""
    parts: list[str] = []
    config = request.config
    if config is not None and config.system_instruction:
        parts.append(str(config.system_instruction))
    for content in request.contents or []:
        parts += [p.text or "" for p in content.parts or []]
    return "\n".join(parts)
