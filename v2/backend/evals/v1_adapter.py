"""Drive V1 (agentic-ai/) with the same scripted personas, for the baseline (spec §14.3).

Runs in V1's own environment (a throwaway `v1-baseline` worktree whose only change is the model
ID), from a temporary working directory because V1 writes files. Email credentials are unset,
so V1 cannot send email.

    <v1 python> -m evals.v1_adapter --v1-dir <worktree>/agentic-ai --run v1-live

V1 has free-text questions, so the simulated user must find which field is being asked. It
uses fixed keyword rules (FIELD_PATTERNS) on V1's message and answers the field mentioned
first, from the same answer book as V2. Choice answers become V1's words ("Family Inquiry",
"Self"). Where the V2 persona would press Skip, it says "I would rather not say." (V1 has no
skip). Metrics that need judgement are heuristics, documented in EVAL_RESULTS.md:
- questions per message = max(number of "?", number of distinct fields mentioned)
- a repeated question = a field asked again after the user already answered it
- completion = V1 saved its JSON record; field accuracy compares that record.

Throttling and request counting use ADK model callbacks set on V1's agent objects at runtime
(V1's code is not changed). V1 makes one request per model call; there is no hedge.
"""

import argparse
import asyncio
import json
import os
import random
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from evals.budget import Budget, DailyLimitReached, Limits  # noqa: E402
from evals.cases import Case, load_cases  # noqa: E402
from evals.common import norm, say  # noqa: E402

RUNS = Path.home() / ".intake-v2" / "evals"
MAX_USER_TURNS = 25
BACKOFF_S = (5.0, 15.0, 45.0)
SKIP_TEXT = "I would rather not say."
CONFIRM_TEXT = "Yes, that is correct."
EXCLUDED = {"pause_resume"}  # V1 has no pause or resume

V1_WORDS = {
    "family_inquiry": "Family Inquiry",
    "provider_referral": "Provider Referral",
    "me": "Self",
    "child": "Parent",
    "parent": "Other Family Member",
    "look_after": "Guardian",
    "email": "Email",
    "phone_call": "Phone",
    "text_message": "Text",
    "letter": "Mail",
    "autism_assessment": "An autism assessment",
    "therapy_support": "Therapy or support",
    "school_work": "Help at school or work",
    "physician": "Physician Referral",
    "specialist": "Specialist Referral",
    "emergency": "Emergency Referral",
    "fax": "Fax",
    "phone": "Phone",
    "web_form": "Webforms",
}

# Checked in this order; a field counts as asked if its pattern appears in V1's message.
FIELD_PATTERNS: list[tuple[str, str]] = [
    (
        "intake_type",
        r"family inquiry.{0,80}provider referral|provider referral.{0,80}family inquiry",
    ),
    (
        "preferred_contact_method",
        r"preferred (contact )?(method|way)|contact method"
        r"|how would you (like|prefer) to be contacted",
    ),
    ("contact_details", r"contact details"),
    (
        "referral_provider_name",
        r"referring provider|provider'?s name|name of the (referring )?provider",
    ),
    ("referral_type", r"type of referral|referral type"),
    ("referral_mode", r"referral mode|mode of (the )?referral|how (was|is) the referral sent"),
    ("referral_date", r"referral date|date of (the )?referral"),
    ("date_of_birth", r"date of birth|birth ?date|\bdob\b"),
    ("relationship", r"relationship"),
    ("inquiry_reason", r"reason for|reason of|inquiry reason"),
    ("gender", r"\bgender\b"),
    ("email", r"e-?mail"),
    ("phone", r"phone number|\bphone\b"),
    ("address", r"(?<!e-mail )(?<!email )\baddress\b"),
    ("full_name", r"\bname\b"),
]
CONFIRM = re.compile(
    r"\b(is (this|that|everything|all (of )?(this|that)) (information )?correct"
    r"|confirm|accurate)\b",
    re.I,
)
# V1 asking the user to type in a fixed format (the "format burden" of audit #9).
FORMAT_DEMAND = re.compile(r"yyyy|xxx-xxx", re.I)
V1_FIELDS = {  # V1's JSON record key -> V2 field
    "client_name": "full_name",
    "client_dob": "date_of_birth",
    "client_email": "email",
    "client_phone": "phone",
    "client_address": "address",
    "referral_provider_name": "referral_provider_name",
    "referral_date": "referral_date",
    "referral_type": "referral_type",
    "referral_mode": "referral_mode",
    "relationship": "relationship",
    "inquiry_reason": "inquiry_reason",
    "preferred_contact_method": "preferred_contact_method",
}


# Words that are part of another field's question, not questions of their own.
SHADOWED = {
    "preferred_contact_method": {"phone", "email"},  # its options: "Phone, Email, Mail, Text"
    "contact_details": {"phone", "email"},
    "referral_provider_name": {"full_name"},  # "the name of the referring provider"
    "referral_mode": {"phone"},  # its options: "Fax, Phone, Webforms"
}


def asked_fields(text: str) -> list[str]:
    low = text.casefold()
    hits = [(m.start(), f) for f, p in FIELD_PATTERNS if (m := re.search(p, low))]
    found = {f for _, f in hits}
    hidden = set().union(*(SHADOWED.get(f, set()) for f in found))
    return [f for _, f in sorted(hits) if f not in hidden]


def questions_in(text: str) -> int:
    return max(text.count("?"), len(set(asked_fields(text))))


def read_message(text: str) -> tuple[bool, list[str]]:
    """(is it a confirmation?, fields asked). A summary that asks "is this correct?" names
    every field but asks one thing: it is a confirmation, not a list of questions."""
    if CONFIRM.search(text):
        return True, []
    return False, asked_fields(text)


def score_turns(turns: list[dict[str, Any]]) -> tuple[list[int], int]:
    """Questions per V1 message, and repeated questions: a field asked again after the user
    already answered it. The same rules as the live conversation, from the stored text."""
    answered: set[str] = set()
    questions, repeated = [], 0
    for turn in turns:
        if "assistant" not in turn:
            continue  # an API failure
        confirming, fields = read_message(turn["assistant"])
        questions.append(1 if confirming else questions_in(turn["assistant"]))
        repeated += len(set(fields) & answered)
        if fields:
            answered.add(fields[0])  # the simulated user answers the field asked first
    return questions, repeated


def answer_for(case: Case, field: str) -> str:
    if field == "contact_details":  # V1-only field: the persona repeats the email it gave
        entry = case.book.get("email")
        return entry.say if entry and entry.say else SKIP_TEXT
    entry = case.book.get(field)
    if entry is None or entry.skip:
        return SKIP_TEXT
    if entry.press:
        return V1_WORDS.get(entry.press, entry.press)
    return entry.say or SKIP_TEXT


def v1_value_matches(field: str, got: str | None, expected: str) -> bool:
    if got is None:
        return False
    if field == "phone":
        return re.sub(r"\D", "", got)[-10:] == re.sub(r"\D", "", expected)[-10:]
    if field in (
        "referral_type",
        "referral_mode",
        "relationship",
        "preferred_contact_method",
        "inquiry_reason",
    ):
        return norm(got) == norm(V1_WORDS.get(expected, expected))
    return norm(got) == norm(expected)


class Meter:
    """Throttle and count every V1 model request through ADK callbacks."""

    def __init__(self, budget: Budget) -> None:
        self.budget = budget
        self.calls: list[dict[str, Any]] = []
        self._started: list[float] = []

    def before(self, callback_context: Any, llm_request: Any) -> None:
        self.budget.before_turn(worst=1)
        self._started.append(time.monotonic())

    def after(self, callback_context: Any, llm_response: Any) -> None:
        started = self._started.pop() if self._started else time.monotonic()
        usage = getattr(llm_response, "usage_metadata", None)
        tokens_in = getattr(usage, "prompt_token_count", None) or 0
        tokens_out = getattr(usage, "candidates_token_count", None) or 0
        self.calls.append(
            {
                "latency_ms": int((time.monotonic() - started) * 1000),
                "input_tokens": tokens_in,
                "output_tokens": tokens_out,
                "error": bool(getattr(llm_response, "error_code", None)),
            }
        )
        self.budget.after_turn(1, tokens_in + tokens_out)

    def attach(self, agent: Any) -> None:
        agent.before_model_callback = self.before
        agent.after_model_callback = self.after
        for sub in getattr(agent, "sub_agents", []) or []:
            self.attach(sub)


async def run_case(case: Case, root_agent: Any, meter: Meter, workdir: Path) -> dict[str, Any]:
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    sessions = InMemorySessionService()
    runner = Runner(app_name="v1_baseline", agent=root_agent, session_service=sessions)
    session_id = uuid.uuid4().hex
    await sessions.create_session(app_name="v1_baseline", user_id="eval", session_id=session_id)
    records = workdir / "collected_chatbot_data"
    before_files = set(records.glob("*.json")) if records.exists() else set()
    calls_before = len(meter.calls)
    turns: list[dict[str, Any]] = []
    used_specials: set[int] = set()
    api_failures, outcome = 0, "incomplete"
    message = "Hello"
    for _ in range(MAX_USER_TURNS):
        text = ""
        tool_calls: list[dict[str, Any]] = []
        for attempt in range(len(BACKOFF_S) + 1):
            try:
                content = types.Content(role="user", parts=[types.Part(text=message)])
                text, tool_calls = "", []
                async for event in runner.run_async(
                    user_id="eval", session_id=session_id, new_message=content
                ):
                    for part in (event.content.parts if event.content else None) or []:
                        if part.text and not getattr(part, "thought", False):
                            text += part.text + "\n"
                        if part.function_call:
                            tool_calls.append(
                                {
                                    "name": part.function_call.name,
                                    "args": dict(part.function_call.args or {}),
                                }
                            )
                break
            except Exception as error:  # an API failure, not a V1 mistake
                api_failures += 1
                turns.append({"user": message, "api_failure": type(error).__name__})
                if attempt == len(BACKOFF_S):
                    outcome = "api_failed"
                    break
                await asyncio.sleep(BACKOFF_S[attempt] * random.uniform(1.0, 1.5))  # noqa: S311
        if outcome == "api_failed":
            break
        confirming, fields = read_message(text)
        turns.append({"user": message, "assistant": text.strip(), "tools": tool_calls})
        if set(records.glob("*.json")) - before_files if records.exists() else False:
            outcome = "saved"
            break
        special = next(
            (
                i
                for i, s in enumerate(case.specials)
                if fields and s.at == fields[0] and i not in used_specials and s.say
            ),
            None,
        )
        if special is not None:
            used_specials.add(special)
            message = case.specials[special].say or ""
        elif confirming:
            message = CONFIRM_TEXT
        elif fields:
            message = answer_for(case, fields[0])
        else:
            message = "Okay."
    new_files = sorted(set(records.glob("*.json")) - before_files) if records.exists() else []
    record = json.loads(new_files[-1].read_text(encoding="utf-8")) if new_files else None
    return {
        "id": case.id,
        "category": case.category,
        "persona": case.persona,
        "intake": case.intake,
        "outcome": outcome,
        "record": record,
        "turns": turns,
        "api_failures": api_failures,
        "llm_calls": meter.calls[calls_before:],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v1-dir", required=True, type=Path)
    parser.add_argument("--run", required=True)
    parser.add_argument("--only", nargs="*")
    parser.add_argument("--per-category", type=int, default=1)
    args = parser.parse_args()
    folder = RUNS / args.run
    workdir = folder / "v1-cwd"
    workdir.mkdir(parents=True, exist_ok=True)
    for var in ("SENDER_EMAIL", "SENDER_PASSWORD", "SMTP_SERVER", "EMAIL_PASSWORD"):
        os.environ.pop(var, None)  # V1 must not be able to send email
    os.environ["GOOGLE_API_KEY"] = _key_from_v2_env()
    os.chdir(workdir)  # V1 writes collected_chatbot_data/ into the working directory
    sys.path.insert(0, str(args.v1_dir.resolve()))
    from agent.root_agent.agent import root_agent  # type: ignore[import-not-found]  # V1

    budget = Budget(RUNS / "quota.json", Limits())
    meter = Meter(budget)
    meter.attach(root_agent)
    results = folder / "results.jsonl"
    done = (
        {json.loads(x)["id"] for x in results.read_text(encoding="utf-8").splitlines() if x}
        if results.exists()
        else set()
    )
    picked: dict[str, int] = {}
    for case in load_cases():
        if case.category in EXCLUDED or (args.only and case.id not in args.only):
            continue
        picked[case.category] = picked.get(case.category, 0) + 1
        if picked[case.category] > args.per_category or case.id in done:
            continue
        started = time.monotonic()
        try:
            result = asyncio.run(run_case(case, root_agent, meter, workdir))
        except DailyLimitReached as stop:
            say(f"Stopped before {case.id}: {stop}. Run again tomorrow to resume.")
            break
        result["duration_s"] = round(time.monotonic() - started, 1)
        with results.open("a", encoding="utf-8") as f:
            f.write(json.dumps(result) + "\n")
        say(
            f"{case.id}: {result['outcome']} ({result['duration_s']} s, "
            f"{budget.used_today()} requests today)"
        )


def _key_from_v2_env() -> str:
    """GOOGLE_API_KEY from v2/backend/.env. Never printed or logged."""
    for line in (BACKEND / ".env").read_text(encoding="utf-8").splitlines():
        name, _, value = line.partition("=")
        if name.strip() == "GOOGLE_API_KEY" and value.strip():
            return value.strip().strip('"').strip("'")
    raise SystemExit("GOOGLE_API_KEY is not set in v2/backend/.env")


if __name__ == "__main__":
    main()
