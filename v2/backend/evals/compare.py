"""V1 vs V2 table (markdown) from the saved runs.

    uv run python -m evals.compare --v1 "v1-live+v1-live-rerun" --v2 "v2-live-1+v2-live-1-rerun"

V2 is shown on the same cases the V1 baseline ran (scored only on fields both versions collect)
and on all its cases. Metrics that do not apply are marked, never estimated.
"""

import argparse
import json
from typing import Any

from evals.common import say
from evals.metrics import load, summarize, summarize_v1
from evals.v1_adapter import V1_FIELDS

LATENCY = "Latency per call p50 / p95 (not comparable, note 1)"
NOTES = (
    "Latency is not comparable: V1 and V2 ran on different days; V1 has no deadline or "
    "hedge, so it waits for slow calls; and the API was slow during part of the V1 run "
    "(calls up to 59 s). Model requests and tokens per intake are the efficiency measures.",
    "The V1 distress case was re-run after an adapter fix: V2's persona presses Keep going "
    "after the distress turn, and V1's persona now says it wants to keep going. The first "
    "attempt stalled because it said nothing equivalent.",
    "V1's 27 retries: phone 9 (not in XXX-XXX-XXXX format), gender 6 ('I would rather not "
    "say'; V1 accepts only Male or Female), address 4, date of birth 4 (YYYY-MM-DD), "
    "contact method 2, name 1, relationship 1. Its 27 repeats: contact details 12 (the email "
    "or phone was already given, audit D3), date of birth 7 (asked again in YYYY-MM-DD after "
    "moving on), and 8 single others.",
    "V1's questions, repeats and retries come from keyword rules on its free-text messages "
    "(evals/v1_adapter.py). After the first V1 run, three false positives were fixed ('the "
    "email agent' and the options inside 'contact details (phone/email/address)' were "
    "counted as questions) and V1 was re-scored from its stored messages.",
)


def _v2_row(s: dict[str, Any]) -> dict[str, str]:
    calls, safety, wording = s["calls"], s["safety"], s["wording"]
    return {
        "Cases": str(s["cases"]),
        "Completion (record saved / form sent)": f"{s['completion_rate']} %",
        "Field accuracy": (
            f"{s['field_accuracy']['overall']} % of {s['field_accuracy']['checked']}"
        ),
        "Repeated questions (asked again after moving on)": str(s["repeated_questions"]),
        "Retries (asked again right after an answer)": str(s["reasked_after_typed_answer"]),
        "Messages asking more than one thing": (
            f"{s['turns_with_more_than_one_question']} of {calls['turns']}"
        ),
        "Reading grade <= 6: (a) system text": (
            f"{wording['a_system_text']['grade_6_or_lower']} %"
        ),
        "Reading grade <= 6: (b) full message": (
            f"{wording['b_full_message']['grade_6_or_lower']} %"
        ),
        "Messages demanding a fixed format": str(s["messages_demanding_a_format"]),
        "Unsafe actions accepted": str(safety["unsafe_accepted"]),
        "Crisis cases reaching a person": (
            f"{safety['crisis_to_needs_human']} %"
            if safety["crisis_to_needs_human"] is not None
            else "no crisis case in this set"
        ),
        "Model requests per intake": f"{calls['requests'] / max(s['cases'], 1):.1f}",
        "Tokens per intake (median)": f"{calls['tokens_per_intake_median']:,.0f}",
        LATENCY: f"{calls['latency_ms_p50']} / {calls['latency_ms_p95']} ms",
        "API failures": str(s["api_failures"]["turns"]),
    }


def _v1_row(s: dict[str, Any]) -> dict[str, str]:
    return {
        "Cases": str(s["cases"]),
        "Completion (record saved / form sent)": f"{s['completion_rate']} %",
        "Field accuracy": f"{s['field_accuracy']} % of {s['fields_checked']}",
        "Repeated questions (asked again after moving on)": str(s["repeated_questions"]),
        "Retries (asked again right after an answer)": str(s["retries_after_refusal"]),
        "Messages asking more than one thing": (
            f"{s['messages_with_more_than_one_question']} of {s['messages']}"
        ),
        "Reading grade <= 6: (a) system text": f"{s['a_system_text_grade_6_or_lower']} %",
        "Reading grade <= 6: (b) full message": f"{s['b_full_message_grade_6_or_lower']} %",
        "Messages demanding a fixed format": str(s["messages_demanding_a_format"]),
        "Unsafe actions accepted": str(s["unsafe_accepted"]),
        "Crisis cases reaching a person": "not tested (V1 has no crisis handling)",
        "Model requests per intake": f"{s['requests'] / max(s['cases'], 1):.1f}",
        "Tokens per intake (median)": f"{s['tokens_per_intake_median']:,.0f}",
        LATENCY: f"{s['latency_ms_p50']} / {s['latency_ms_p95']} ms",
        "API failures": str(s["api_failures"]),
    }


def table(v1_run: str, v2_run: str) -> str:
    v1 = summarize_v1(v1_run)
    same = {r["id"] for r in load(v1_run)} & {r["id"] for r in load(v2_run)}
    both = set(V1_FIELDS.values())  # fields both versions collect
    v2_same, v2_all = summarize(v2_run, only=same, fields=both), summarize(v2_run)
    rows = [_v1_row(v1), _v2_row(v2_same), _v2_row(v2_all)]
    header = "| Metric | V1 | V2, same cases | V2, all cases |\n|---|---|---|---|\n"
    body = "".join(
        f"| {metric} | {rows[0][metric]} | {rows[1][metric]} | {rows[2][metric]} |\n"
        for metric in rows[0]
    )
    notes = "".join(f"{i}. {note}\n" for i, note in enumerate(NOTES, start=1))
    return f"{header}{body}\n{notes}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v1", required=True)
    parser.add_argument("--v2", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.json:
        say(json.dumps({"v1": summarize_v1(args.v1)}, indent=2))
    say(table(args.v1, args.v2))


if __name__ == "__main__":
    main()
