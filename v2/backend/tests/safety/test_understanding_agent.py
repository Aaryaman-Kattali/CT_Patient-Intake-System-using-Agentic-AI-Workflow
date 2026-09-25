"""The real ADK agent, driven by a scripted model (no network)."""

import os
from pathlib import Path

import pytest

from app.agents.understanding_agent import AdkUnderstander, build_agent
from app.domain.types import InputType
from app.workflow.understanding import (
    FieldBrief,
    ReplyKind,
    UnderstandingContext,
)
from tests.agent_helpers import SLEEP, ScriptedLlm, request_text

TEST_TIMEOUT = 30.0  # generous: the first ADK call in a cold CI process can be slow

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
    reply = AdkUnderstander(llm, timeout_s=TEST_TIMEOUT).understand(
        "Alex Rivera, May 4 2004", CONTEXT
    )
    assert reply.understanding is not None
    assert reply.understanding.kind is ReplyKind.ANSWER_PLUS_EXTRA
    assert [p.field_id for p in reply.understanding.proposals] == ["full_name", "date_of_birth"]
    assert (reply.call.status, reply.call.input_tokens, reply.call.output_tokens) == ("ok", 120, 30)
    assert reply.call.model == "scripted-test-model"


def test_structured_output_schema_is_sent_to_the_model() -> None:
    llm = ScriptedLlm().reply_with(GOOD)
    AdkUnderstander(llm, timeout_s=TEST_TIMEOUT).understand("Alex Rivera", CONTEXT)
    config = llm.requests[0].config
    assert config is not None
    assert config.response_schema is not None or config.response_json_schema is not None
    assert config.temperature == 0.0


def test_bad_json_is_retried_once_then_fails_closed() -> None:
    llm = ScriptedLlm().reply_with("not json", "still not json")
    reply = AdkUnderstander(llm, timeout_s=TEST_TIMEOUT).understand("Alex Rivera", CONTEXT)
    assert reply.understanding is None
    assert (reply.call.status, reply.call.attempts) == ("parse_error", 2)


def test_retry_succeeds_on_second_attempt() -> None:
    llm = ScriptedLlm().reply_with('{"kind": "answer"', GOOD)
    reply = AdkUnderstander(llm, timeout_s=TEST_TIMEOUT).understand("Alex Rivera", CONTEXT)
    assert reply.understanding is not None
    assert reply.call.attempts == 2


def test_timeout_fails_closed() -> None:
    llm = ScriptedLlm().reply_with(SLEEP, SLEEP)
    reply = AdkUnderstander(llm, timeout_s=0.2).understand("Alex Rivera", CONTEXT)
    assert reply.understanding is None
    assert reply.call.status == "timeout"


def test_unknown_kind_from_model_is_a_parse_error() -> None:
    llm = ScriptedLlm().reply_with(
        {"kind": "send_email", "proposals": []}, {"kind": "x", "proposals": []}
    )
    assert (
        AdkUnderstander(llm, timeout_s=TEST_TIMEOUT).understand("hi", CONTEXT).understanding is None
    )


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
    AdkUnderstander(llm, timeout_s=TEST_TIMEOUT).understand("Alex Rivera", CONTEXT)
    sent = request_text(llm.requests[0])
    assert "Alex Rivera" in sent  # the current message, inside <user_message>
    assert sent.count("Alex Rivera") == 1
    assert "answered_field_ids" in sent
    assert "family_inquiry" not in sent  # stored values are never sent, only field ids


def test_each_call_is_stateless() -> None:
    llm = ScriptedLlm().reply_with(GOOD, GOOD)
    understander = AdkUnderstander(llm, timeout_s=TEST_TIMEOUT)
    understander.understand("first message Alex Rivera", CONTEXT)
    understander.understand("second message", CONTEXT)
    assert "first message" not in request_text(llm.requests[1])


def test_agents_do_not_write_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    llm = ScriptedLlm().reply_with(GOOD, "bad", "bad")
    understander = AdkUnderstander(llm, timeout_s=TEST_TIMEOUT)
    understander.understand("Alex Rivera", CONTEXT)
    understander.understand("Alex Rivera", CONTEXT)
    assert os.listdir(tmp_path) == []
