"""A scripted model that plugs into the real ADK LlmAgent + Runner. No network, no key."""

import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Any

from google.adk.models import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from pydantic import PrivateAttr

SLEEP = "__sleep__"


class ScriptedLlm(BaseLlm):
    model: str = "scripted-test-model"
    _replies: list[str] = PrivateAttr(default_factory=list)
    _requests: list[LlmRequest] = PrivateAttr(default_factory=list)

    def reply_with(self, *replies: str | dict[str, Any]) -> "ScriptedLlm":
        self._replies.extend(r if isinstance(r, str) else json.dumps(r) for r in replies)
        return self

    @property
    def requests(self) -> list[LlmRequest]:
        return self._requests

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        self._requests.append(llm_request)
        text = self._replies.pop(0) if self._replies else "{}"
        if text == SLEEP:
            await asyncio.sleep(5)
        yield LlmResponse(
            content=types.Content(role="model", parts=[types.Part(text=text)]),
            usage_metadata=types.GenerateContentResponseUsageMetadata(
                prompt_token_count=120, candidates_token_count=30
            ),
        )


def request_text(request: LlmRequest) -> str:
    """Everything the model was sent: system instruction plus contents."""
    parts: list[str] = []
    config = request.config
    if config is not None and config.system_instruction:
        parts.append(str(config.system_instruction))
    for content in request.contents or []:
        parts += [p.text or "" for p in content.parts or []]
    return "\n".join(parts)
