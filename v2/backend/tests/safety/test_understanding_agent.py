"""The real ADK agent, driven by a scripted model (no network)."""

import asyncio
import os
import time
from pathlib import Path

import pytest

from app.agents.understanding_agent import (
    APP_NAME,
    AdkUnderstander,
    NoKeyUnderstander,
    build_agent,
    build_understander,
)
from app.config import Settings
from app.domain.types import InputType
from app.workflow.understanding import (
    AgentReply,
    FieldBrief,
    ReplyKind,
    UnderstandingContext,
)
from tests.agent_helpers import (
    RAISE,
    SLEEP,
    ApiError,
    ScriptedLlm,
    Slow,
    make_understander,
    request_text,
)

CONTEXT = UnderstandingContext(
    pending=FieldBrief(id="full_name", description="full name", input_type=InputType.TEXT),
    applicable=(
        FieldBrief(id="full_name", description="full name", input_type=InputType.TEXT),
        FieldBrief(id="date_of_birth", description="date of birth", input_type=InputType.DATE),
    ),
    answered_field_ids=("intake_type", "relationship"),
)
GOOD = {
    "kind": "answer_plus_extra",
    "proposals": [
        {
            "field_id": "full_name",
            "raw_text": "Alex Rivera",
            "value": "Alex Rivera",
            "source": "explicit",
        },
        {
            "field_id": "date_of_birth",
            "raw_text": "May 4 2004",
            "value": "2004-05-04",
            "source": "explicit",
        },
    ],
}


def test_agent_parses_structured_output_and_reports_usage() -> None:
    llm = ScriptedLlm().reply_with(GOOD)
    reply = make_understander(llm).understand("Alex Rivera, May 4 2004", CONTEXT)
    assert reply.understanding is not None
    assert reply.understanding.kind is ReplyKind.ANSWER_PLUS_EXTRA
    assert [p.field_id for p in reply.understanding.proposals] == ["full_name", "date_of_birth"]
    assert (reply.call.status, reply.call.input_tokens, reply.call.output_tokens) == ("ok", 120, 30)
    assert reply.call.model == "scripted-test-model"


def test_structured_output_schema_is_sent_to_the_model() -> None:
    llm = ScriptedLlm().reply_with(GOOD)
    make_understander(llm).understand("Alex Rivera", CONTEXT)
    config = llm.requests[0].config
    assert config is not None
    assert config.response_schema is not None or config.response_json_schema is not None
    assert config.temperature == 0.0


def test_bad_json_is_retried_once_then_fails_closed() -> None:
    llm = ScriptedLlm().reply_with("not json", "still not json")
    reply = make_understander(llm).understand("Alex Rivera", CONTEXT)
    assert reply.understanding is None
    assert (reply.call.status, reply.call.attempts) == ("parse_error", 2)


def test_retry_succeeds_on_second_attempt() -> None:
    llm = ScriptedLlm().reply_with('{"kind": "answer"', GOOD)
    reply = make_understander(llm).understand("Alex Rivera", CONTEXT)
    assert reply.understanding is not None
    assert reply.call.attempts == 2


def test_one_understander_serves_many_calls_on_one_loop() -> None:
    """Built once and reused: calls after a deadline still work (no per-call event loop)."""
    llm = ScriptedLlm().reply_with(GOOD, SLEEP, GOOD)
    understander = make_understander(llm, deadline_s=3.0)
    try:
        replies = [understander.understand("Alex Rivera", CONTEXT) for _ in range(3)]
    finally:
        understander.close()
    assert [r.call.status for r in replies] == ["ok", "timeout", "ok"]


# --- hedged requests (docs/V2_SPEC.md §6) -------------------------------------------------

OTHER = {"kind": "off_topic", "proposals": []}


def _call(reply: AgentReply) -> tuple[str, int, bool, int | None]:
    return reply.call.status, reply.call.attempts, reply.call.hedged, reply.call.winner


def _open_sessions(understander: AdkUnderstander) -> int:
    listing = understander._sessions.list_sessions(app_name=APP_NAME, user_id="intake")
    return len(asyncio.run_coroutine_threadsafe(listing, understander._loop).result().sessions)


def test_fast_reply_needs_no_hedge() -> None:
    llm = ScriptedLlm().reply_with(GOOD)
    reply = make_understander(llm, hedge_after_s=5.0).understand("Alex Rivera", CONTEXT)
    assert _call(reply) == ("ok", 1, False, 1)
    assert len(llm.requests) == 1


def test_slow_first_request_hedge_wins() -> None:
    llm = ScriptedLlm().reply_with(Slow(3.0, OTHER), GOOD)
    reply = make_understander(llm, hedge_after_s=0.3).understand("Alex Rivera", CONTEXT)
    assert _call(reply) == ("ok", 2, True, 2)
    assert reply.understanding is not None
    assert reply.understanding.kind is ReplyKind.ANSWER_PLUS_EXTRA  # the hedge's reply
    assert reply.call.latency_ms < 2500


def test_both_requests_slow_end_at_the_deadline() -> None:
    llm = ScriptedLlm().reply_with(SLEEP, SLEEP)
    reply = make_understander(llm, deadline_s=1.0, hedge_after_s=0.2).understand("Alex", CONTEXT)
    assert reply.understanding is None
    assert _call(reply) == ("timeout", 2, True, None)
    assert 900 <= reply.call.latency_ms < 2000


def test_cancelled_request_never_writes_a_result() -> None:
    llm = ScriptedLlm().reply_with(Slow(1.0, OTHER), GOOD)
    understander = make_understander(llm, hedge_after_s=0.2)
    reply = understander.understand("Alex Rivera", CONTEXT)
    time.sleep(1.5)  # well past the moment the slow request would have answered
    assert reply.understanding is not None
    assert reply.understanding.kind is ReplyKind.ANSWER_PLUS_EXTRA
    assert llm.finished == [2]  # request 1 was cancelled before it produced anything
    assert _open_sessions(understander) == 0  # and its session was cleaned up


@pytest.mark.parametrize("code", [429, 500, 503])
def test_transient_api_error_is_retried_once(code: int) -> None:
    llm = ScriptedLlm().reply_with(ApiError(code), GOOD)
    reply = make_understander(llm).understand("Alex Rivera", CONTEXT)
    assert _call(reply) == ("ok", 2, False, 2)


def test_transient_error_twice_fails_with_its_error_class() -> None:
    llm = ScriptedLlm().reply_with(ApiError(429), ApiError(429), GOOD)
    reply = make_understander(llm).understand("Alex Rivera", CONTEXT)
    assert _call(reply) == ("error", 2, False, None)
    assert reply.call.error_class == "ClientError:429"
    assert len(llm.requests) == 2


@pytest.mark.parametrize("code", [400, 401, 403, 404])
def test_other_client_errors_are_not_retried(code: int) -> None:
    llm = ScriptedLlm().reply_with(ApiError(code), GOOD)
    reply = make_understander(llm).understand("Alex Rivera", CONTEXT)
    assert _call(reply) == ("error", 1, False, None)
    assert reply.call.error_class == f"ClientError:{code}"
    assert len(llm.requests) == 1


def test_retry_waits_about_one_second_with_jitter() -> None:
    llm = ScriptedLlm().reply_with(ApiError(503), GOOD)
    reply = make_understander(llm, retry_delay_s=1.0).understand("Alex Rivera", CONTEXT)
    assert reply.call.status == "ok"
    assert 1000 <= reply.call.latency_ms < 3000


def test_no_hedge_for_a_while_after_a_429() -> None:
    llm = ScriptedLlm().reply_with(ApiError(429), GOOD, Slow(1.0, GOOD), Slow(3.0, OTHER), GOOD)
    understander = make_understander(llm, hedge_after_s=0.2, cooldown_after_429_s=1.5)
    first = understander.understand("Alex Rivera", CONTEXT)  # 429, then the retry works
    assert _call(first) == ("ok", 2, False, 2)
    during = understander.understand("Alex Rivera", CONTEXT)  # slow, but no second request
    assert _call(during) == ("ok", 1, False, 1)
    assert during.call.hedge_suppressed
    assert len(llm.requests) == 3
    time.sleep(1.6)  # the cooldown has passed: hedging is back
    after = understander.understand("Alex Rivera", CONTEXT)
    assert _call(after) == ("ok", 2, True, 2)
    assert not after.call.hedge_suppressed


def test_no_retry_when_the_delay_would_pass_the_deadline() -> None:
    llm = ScriptedLlm().reply_with(ApiError(503), GOOD)
    understander = make_understander(llm, deadline_s=3.0, retry_delay_s=5.0)
    reply = understander.understand("Alex Rivera", CONTEXT)
    assert _call(reply) == ("error", 1, False, None)
    assert reply.call.error_class == "ServerError:503"


def test_non_api_error_is_not_retried() -> None:
    llm = ScriptedLlm().reply_with(RAISE, GOOD)
    reply = make_understander(llm).understand("Alex Rivera", CONTEXT)
    assert reply.understanding is None
    assert (reply.call.status, reply.call.attempts) == ("error", 1)
    assert reply.call.error_class == "ConnectionError"


@pytest.mark.parametrize("key", [None, "", "   "])
def test_no_key_never_calls_the_model(key: str | None) -> None:
    understander = build_understander(Settings(google_api_key=key))
    assert isinstance(understander, NoKeyUnderstander)
    reply = understander.understand("Alex Rivera", CONTEXT)
    assert reply.understanding is None
    assert reply.call.status == "no_key"


def test_unknown_kind_from_model_is_a_parse_error() -> None:
    llm = ScriptedLlm().reply_with(
        {"kind": "send_email", "proposals": []}, {"kind": "x", "proposals": []}
    )
    assert make_understander(llm).understand("hi", CONTEXT).understanding is None


# --- B1 / B2 / B3: the agent's surface ---------------------------------------------------


def test_agent_has_no_side_effect_tools() -> None:
    agent = build_agent(ScriptedLlm())
    assert agent.tools == []
    assert agent.sub_agents == []
    assert agent.disallow_transfer_to_parent
    assert agent.disallow_transfer_to_peers


def test_agent_has_no_read_tools_and_no_memory() -> None:
    agent = build_agent(ScriptedLlm())
    assert agent.tools == []
    assert agent.include_contents == "none"  # no conversation history
    assert agent.output_key is None  # writes nothing into shared state


def test_agent_input_contains_no_stored_values() -> None:
    llm = ScriptedLlm().reply_with(GOOD)
    make_understander(llm).understand("Alex Rivera", CONTEXT)
    sent = request_text(llm.requests[0])
    assert "Alex Rivera" in sent  # the current message, inside <user_message>
    assert sent.count("Alex Rivera") == 1
    assert "answered_field_ids" in sent
    assert "family_inquiry" not in sent  # stored values are never sent, only field ids


def test_each_call_is_stateless() -> None:
    llm = ScriptedLlm().reply_with(GOOD, GOOD)
    understander = make_understander(llm)
    understander.understand("first message Alex Rivera", CONTEXT)
    understander.understand("second message", CONTEXT)
    assert "first message" not in request_text(llm.requests[1])


def test_agents_do_not_write_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    llm = ScriptedLlm().reply_with(GOOD, "bad", "bad")
    understander = make_understander(llm)
    understander.understand("Alex Rivera", CONTEXT)
    understander.understand("Alex Rivera", CONTEXT)
    assert os.listdir(tmp_path) == []
