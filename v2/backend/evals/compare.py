"""V1 vs V2 table (markdown) from the saved runs.

    uv run python -m evals.compare --v1 v1-live --v2 "v2-live-1+v2-live-1-rerun"

V2 is shown on the same cases the V1 baseline ran, and on all its cases. Metrics that do not
apply to V1 (it has no fixed crisis response, no hedge) are marked "n/a", never estimated.
"""

import argparse
import json
from typing import Any

from evals.common import say
from evals.metrics import load, summarize, summarize_v1
from evals.v1_adapter import V1_FIELDS


def _v2_row(s: dict[str, Any]) -> dict[str, str]:
    calls, safety, wording = s["calls"], s["safety"], s["wording"]
    turns = calls["turns"]
    return {
        "Cases": str(s["cases"]),
        "Completion (record saved / form sent)": f"{s['completion_rate']} %",
        "Field accuracy": (
            f"{s['field_accuracy']['overall']} % of {s['field_accuracy']['checked']}"
        ),
        "Asked again after an answer (repeats + retries)": (
            f"{s['repeated_questions']} + {s['reasked_after_typed_answer']}"
        ),
        "Messages asking more than one thing": (
            f"{s['turns_with_more_than_one_question']} of {turns}"
        ),
        "Reading grade <= 6: (a) system text": (
            f"{wording['a_system_text']['grade_6_or_lower']} %"
        ),
        "Reading grade <= 6: (b) full message": (
            f"{wording['b_full_message']['grade_6_or_lower']} %"
        ),
        "Messages demanding a fixed format": str(s["messages_demanding_a_format"]),
        "Unsafe actions accepted": str(safety["unsafe_accepted"]),
        "Crisis reaching a person / fixed response": (
            f"{safety['crisis_to_needs_human']} %"
            if safety["crisis_to_needs_human"] is not None
            else "no crisis case"
        ),
        "Model requests per intake": f"{calls['requests'] / max(s['cases'], 1):.1f}",
        "Tokens per intake (median)": f"{calls['tokens_per_intake_median']:,.0f}",
        "Latency per call p50 / p95": f"{calls['latency_ms_p50']} / {calls['latency_ms_p95']} ms",
        "API failures": str(s["api_failures"]["turns"]),
    }


def _v1_row(s: dict[str, Any]) -> dict[str, str]:
    return {
        "Cases": str(s["cases"]),
        "Completion (record saved / form sent)": f"{s['completion_rate']} %",
        "Field accuracy": f"{s['field_accuracy']} % of {s['fields_checked']}",
        "Asked again after an answer (repeats + retries)": (
            f"{s['repeated_questions']} (not separable)"
        ),
        "Messages asking more than one thing": (
            f"{s['messages_with_more_than_one_question']} of {s['messages']}"
        ),
        "Reading grade <= 6: (a) system text": f"{s['a_system_text_grade_6_or_lower']} %",
        "Reading grade <= 6: (b) full message": f"{s['b_full_message_grade_6_or_lower']} %",
        "Messages demanding a fixed format": str(s["messages_demanding_a_format"]),
        "Unsafe actions accepted": str(s["unsafe_accepted"]),
        "Crisis reaching a person / fixed response": "n/a (no crisis handling)",
        "Model requests per intake": f"{s['requests'] / max(s['cases'], 1):.1f}",
        "Tokens per intake (median)": f"{s['tokens_per_intake_median']:,.0f}",
        "Latency per call p50 / p95": f"{s['latency_ms_p50']} / {s['latency_ms_p95']} ms",
        "API failures": str(s["api_failures"]),
    }


def table(v1_run: str, v2_run: str) -> str:
    v1 = summarize_v1(v1_run)
    same = {r["id"] for r in load(v1_run)} & {r["id"] for r in load(v2_run)}
    both = set(V1_FIELDS.values())  # fields both versions collect
    v2_same, v2_all = summarize(v2_run, only=same, fields=both), summarize(v2_run)
    rows = [_v1_row(v1), _v2_row(v2_same), _v2_row(v2_all)]
    header = "| Metric | V1 | V2, same cases | V2, all cases |\n|---|---|---|---|\n"
    return header + "".join(
        f"| {metric} | {rows[0][metric]} | {rows[1][metric]} | {rows[2][metric]} |\n"
        for metric in rows[0]
    )


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
