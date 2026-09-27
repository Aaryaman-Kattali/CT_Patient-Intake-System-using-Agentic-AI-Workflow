"""The understanding agent: an ADK LlmAgent with Gemini structured output and no tools.

It receives the reply plus a description of the form (field ids and types, never stored
values) and returns a proposal. The application validates and decides (docs/V2_SPEC.md §6).
"""

import asyncio
import concurrent.futures
import functools
import json
import logging
import threading
import time
import uuid
from enum import StrEnum

from google.adk.agents import LlmAgent
from google.adk.models import BaseLlm
from google.adk.models.google_llm import Gemini
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel, ValidationError

from app.agents.hedging import AttemptResult, Cooldown, HedgeOutcome, HedgePolicy, hedged_call
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
LOOP_GRACE_S = 2.0  # only if the event loop itself is stuck; the deadline is enforced inside


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
    if settings.google_api_key is None:
        raise ValueError("GOOGLE_API_KEY is not set; use NoKeyUnderstander")
    key = settings.google_api_key.get_secret_value()
    return Gemini(model=settings.gemini_model, client_kwargs={"api_key": key})


def classify_error(error: Exception) -> tuple[str, bool]:
    """(error class for llm_calls, transient?). Only 429 and 5xx are worth retrying."""
    if isinstance(error, genai_errors.APIError):
        base = (
            "ServerError"
            if isinstance(error, genai_errors.ServerError)
            else "ClientError"
            if isinstance(error, genai_errors.ClientError)
            else "APIError"
        )
        return f"{base}:{error.code}", error.code == 429 or 500 <= error.code < 600
    return type(error).__name__, False


class AdkUnderstander:
    """Built once. All calls run on one long-lived event loop in a background thread, so the
    Gemini client's connections stay valid between calls (a new loop per call breaks them).
    Each turn is one hedged call with an overall deadline (see app/agents/hedging.py).
    """

    def __init__(self, model: BaseLlm, policy: HedgePolicy) -> None:
        self._model_name = model.model
        self._policy = policy
        self._cooldown = Cooldown(policy.cooldown_after_429_s)  # process-level: built once
        self._sessions = InMemorySessionService()
        self.agent = build_agent(model)
        self._runner = Runner(app_name=APP_NAME, agent=self.agent, session_service=self._sessions)
        self._loop = asyncio.new_event_loop()
        threading.Thread(target=self._loop.run_forever, name="understanding", daemon=True).start()

    def close(self) -> None:
        self._loop.call_soon_threadsafe(self._loop.stop)

    def understand(self, message: str, context: UnderstandingContext) -> AgentReply:
        prompt = build_prompt(message, context)
        started = time.monotonic()
        call = hedged_call(
            functools.partial(self._attempt, prompt),
            self._policy,
            may_hedge=lambda: not self._cooldown.active(),
        )
        future = asyncio.run_coroutine_threadsafe(call, self._loop)
        try:
            outcome = future.result(timeout=self._policy.deadline_s + LOOP_GRACE_S)
        except concurrent.futures.TimeoutError:  # the loop itself is stuck: fail closed
            future.cancel()
            outcome = HedgeOutcome(None, "timeout", attempts=0, hedged=False)
        return AgentReply(understanding=outcome.value, call=self._info(outcome, started))

    def _info(self, outcome: HedgeOutcome[ReplyUnderstanding], started: float) -> LlmCallInfo:
        return LlmCallInfo(
            model=self._model_name,
            input_tokens=outcome.usage[0],
            output_tokens=outcome.usage[1],
            latency_ms=int((time.monotonic() - started) * 1000),
            status=outcome.status,
            attempts=outcome.attempts,
            hedged=outcome.hedged,
            winner=outcome.winner,
            hedge_suppressed=outcome.hedge_suppressed,
            error_class=outcome.error_class,
        )

    async def _attempt(self, prompt: str) -> AttemptResult[ReplyUnderstanding]:
        """One request. Never raises, except when cancelled."""
        try:
            text, usage = await self._run(prompt)
        except Exception as error:  # network or SDK error: reported, never crashes the turn
            error_class, transient = classify_error(error)
            if error_class.endswith(":429"):
                self._cooldown.start()
            log.warning(
                "understanding attempt failed: %s", error_class, extra={"error_class": error_class}
            )
            return AttemptResult(failure="error", error_class=error_class, transient=transient)
        try:
            parsed = LlmReply.model_validate_json(text).to_understanding()
        except (ValidationError, ValueError):
            return AttemptResult(usage=usage, failure="parse_error")
        return AttemptResult(value=parsed, usage=usage)

    async def _run(self, prompt: str) -> tuple[str, tuple[int | None, int | None]]:
        """One stateless run: a fresh session, deleted afterwards (also when cancelled)."""
        session_id = uuid.uuid4().hex
        await self._sessions.create_session(
            app_name=APP_NAME, user_id="intake", session_id=session_id
        )
        try:
            return await self._call(session_id, prompt)
        finally:
            await self._sessions.delete_session(
                app_name=APP_NAME, user_id="intake", session_id=session_id
            )

    async def _call(
        self, session_id: str, prompt: str
    ) -> tuple[str, tuple[int | None, int | None]]:
        text = ""
        usage: tuple[int | None, int | None] = (None, None)
        content = types.Content(role="user", parts=[types.Part(text=prompt)])
        async for event in self._runner.run_async(
            user_id="intake", session_id=session_id, new_message=content
        ):
            if event.usage_metadata:
                meta = event.usage_metadata
                usage = (meta.prompt_token_count, meta.candidates_token_count)
            if event.is_final_response() and event.content and event.content.parts:
                text = "".join(p.text or "" for p in event.content.parts if not p.thought)
        return text, usage


class NoKeyUnderstander:
    """Used when GOOGLE_API_KEY is not set: never calls the network, always fails closed."""

    def __init__(self, model_name: str) -> None:
        self._model_name = model_name

    def understand(self, message: str, context: UnderstandingContext) -> AgentReply:
        return AgentReply(
            understanding=None,
            call=LlmCallInfo(model=self._model_name, latency_ms=0, status="no_key", attempts=0),
        )


def build_understander(settings: Settings) -> AdkUnderstander | NoKeyUnderstander:
    if settings.google_api_key is None:
        return NoKeyUnderstander(settings.gemini_model)
    policy = HedgePolicy(
        deadline_s=settings.llm_deadline_s, hedge_after_s=settings.llm_hedge_after_s
    )
    return AdkUnderstander(gemini_model(settings), policy)
