"""The understanding agent: an ADK LlmAgent with Gemini structured output and no tools.

It receives the reply plus a description of the form (field ids and types, never stored
values) and returns a proposal. The application validates and decides (docs/V2_SPEC.md §6).
"""

import asyncio
import json
import logging
import time
import uuid
from enum import StrEnum
from typing import Literal

from google.adk.agents import LlmAgent
from google.adk.models import BaseLlm
from google.adk.models.google_llm import Gemini
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel, ValidationError

from app.agents.prompts import UNDERSTANDING_INSTRUCTION
from app.config import Settings
from app.workflow.understanding import (
    AgentReply,
    FieldProposal,
    LlmCallInfo,
    ReplyKind,
    ReplyUnderstanding,
    UnderstandingContext,
)

log = logging.getLogger(__name__)

APP_NAME = "intake_understanding"
CallStatus = Literal["ok", "parse_error", "timeout", "error"]
MAX_ATTEMPTS = 2  # one retry on a parse error or timeout (spec §10.2)


# --- the schema Gemini must fill (plain lists and enums only) ------------------------


class LlmSource(StrEnum):
    EXPLICIT = "explicit"
    INFERRED = "inferred"


class LlmClarification(StrEnum):
    WHY = "why"
    MEANING = "meaning"


class LlmDistress(StrEnum):
    OVERWHELMED = "overwhelmed"
    CRISIS = "crisis"


class LlmProposal(BaseModel):
    field_id: str
    raw_text: str
    value: str
    source: LlmSource


class LlmReply(BaseModel):
    kind: ReplyKind
    proposals: list[LlmProposal]
    clarification: LlmClarification | None = None
    distress_level: LlmDistress | None = None

    def to_understanding(self) -> ReplyUnderstanding:
        return ReplyUnderstanding(
            kind=self.kind,
            proposals=tuple(
                FieldProposal(
                    field_id=p.field_id,
                    raw_text=p.raw_text,
                    value=p.value,
                    source=p.source.value,
                )
                for p in self.proposals
            ),
            clarification=self.clarification.value if self.clarification else None,
            distress_level=self.distress_level.value if self.distress_level else None,
        )


def build_prompt(message: str, context: UnderstandingContext) -> str:
    return (
        "<context>\n"
        + json.dumps(context.model_dump(mode="json"), ensure_ascii=False)
        + "\n</context>\n<user_message>\n"
        + message
        + "\n</user_message>"
    )


def build_agent(model: BaseLlm | str) -> LlmAgent:
    """No tools, no sub-agents, no transfers, no conversation history, no output_key."""
    return LlmAgent(
        name="understanding_agent",
        model=model,
        instruction=UNDERSTANDING_INSTRUCTION,
        output_schema=LlmReply,
        include_contents="none",
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
        generate_content_config=types.GenerateContentConfig(temperature=0.0),
    )


def gemini_model(settings: Settings) -> BaseLlm:
    key = settings.google_api_key.get_secret_value() if settings.google_api_key else None
    return Gemini(model=settings.gemini_model, client_kwargs={"api_key": key} if key else {})


class AdkUnderstander:
    def __init__(self, model: BaseLlm, timeout_s: float) -> None:
        self._model_name = model.model
        self._timeout_s = timeout_s
        self._sessions = InMemorySessionService()
        self.agent = build_agent(model)
        self._runner = Runner(app_name=APP_NAME, agent=self.agent, session_service=self._sessions)

    def understand(self, message: str, context: UnderstandingContext) -> AgentReply:
        prompt = build_prompt(message, context)
        started = time.monotonic()
        status: CallStatus = "error"
        usage: tuple[int | None, int | None] = (None, None)
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                text, usage = asyncio.run(asyncio.wait_for(self._run(prompt), self._timeout_s))
                parsed = LlmReply.model_validate_json(text).to_understanding()
            except TimeoutError:
                status = "timeout"
                continue
            except (ValidationError, ValueError):
                status = "parse_error"
                continue
            except Exception:  # network or SDK error: fail closed, never crash the turn
                log.exception("understanding call failed")
                status = "error"
                break
            return AgentReply(understanding=parsed, call=self._info("ok", started, usage, attempt))
        return AgentReply(understanding=None, call=self._info(status, started, usage, attempt))

    def _info(
        self,
        status: CallStatus,
        started: float,
        usage: tuple[int | None, int | None],
        attempts: int,
    ) -> LlmCallInfo:
        return LlmCallInfo(
            model=self._model_name,
            input_tokens=usage[0],
            output_tokens=usage[1],
            latency_ms=int((time.monotonic() - started) * 1000),
            status=status,
            attempts=attempts,
        )

    async def _run(self, prompt: str) -> tuple[str, tuple[int | None, int | None]]:
        """One stateless run: a fresh session, deleted afterwards."""
        session_id = uuid.uuid4().hex
        await self._sessions.create_session(
            app_name=APP_NAME, user_id="intake", session_id=session_id
        )
        text = ""
        usage: tuple[int | None, int | None] = (None, None)
        try:
            content = types.Content(role="user", parts=[types.Part(text=prompt)])
            async for event in self._runner.run_async(
                user_id="intake", session_id=session_id, new_message=content
            ):
                if event.usage_metadata:
                    meta = event.usage_metadata
                    usage = (meta.prompt_token_count, meta.candidates_token_count)
                if event.is_final_response() and event.content and event.content.parts:
                    text = "".join(p.text or "" for p in event.content.parts if not p.thought)
        finally:
            await self._sessions.delete_session(
                app_name=APP_NAME, user_id="intake", session_id=session_id
            )
        return text, usage


def build_understander(settings: Settings) -> AdkUnderstander:
    return AdkUnderstander(gemini_model(settings), timeout_s=settings.llm_timeout_s)
