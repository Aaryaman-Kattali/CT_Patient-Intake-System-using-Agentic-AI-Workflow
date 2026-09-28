"""The eval harness itself: request budget, dataset, and a resumable dry run (no API calls)."""

import json
import re
from collections import Counter
from pathlib import Path

import pytest

import evals.runner as runner
from app.config import Settings
from evals.budget import EVAL_RPD, EVAL_RPM, EVAL_TPM, Budget, DailyLimitReached, Limits
from evals.cases import load_cases
from tests.e2e_server import RuleUnderstander


class FakeTime:
    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def test_limits_are_70_percent_of_rpm_and_tpm_and_80_percent_of_rpd() -> None:
    assert (EVAL_RPM, EVAL_TPM, EVAL_RPD) == (10, 175_000, 400)


def test_budget_waits_when_the_minute_is_full(tmp_path: Path) -> None:
    t = FakeTime()
    budget = Budget(tmp_path / "b.json", Limits(), clock=t.clock, sleep=t.sleep, today=lambda: "d1")
    budget.before_turn()
    budget.after_turn(requests=6, tokens=7_000)  # 6 + worst case 4 = 10: still fits
    budget.before_turn()
    assert t.slept == []
    budget.after_turn(requests=1, tokens=1_200)  # 7 + 4 > 10: must wait for the window
    budget.before_turn()
    assert t.slept
    assert t.now >= 60


def test_budget_stops_cleanly_at_the_daily_limit_and_resets_next_day(tmp_path: Path) -> None:
    day = ["d1"]
    t = FakeTime()
    budget = Budget(
        tmp_path / "b.json",
        Limits(rpm=10**6, tpm=10**9, rpd=10),
        clock=t.clock,
        sleep=t.sleep,
        today=lambda: day[0],
    )
    budget.after_turn(requests=7, tokens=0)
    with pytest.raises(DailyLimitReached):
        budget.before_turn()  # 7 + worst case 4 > 10
    again = Budget(tmp_path / "b.json", Limits(rpd=10), today=lambda: day[0])
    assert again.used_today() == 7  # saved on disk: a restarted run knows
    day[0] = "d2"
    assert again.used_today() == 0


def test_dataset_is_61_synthetic_cases_across_14_categories() -> None:
    cases = load_cases()
    assert len(cases) == 61  # 60 original + 1 added after run 1
    assert len(Counter(c.category for c in cases)) == 14
    assert [c.id for c in cases if c.added] == ["different_question-61"]
    text = json.dumps([c.model_dump(mode="json") for c in cases])
    emails = re.findall(r"[\w.+-]+@([\w-]+\.)+\w+", text)
    assert emails
    assert all(
        re.search(r"@example\.(com|org|net)$", m.group(0))
        for m in re.finditer(r"[\w.+-]+@[\w.-]+\.\w+", text)
    )
    phones = re.findall(r"202.?555.?(\d{4})", text)
    assert phones
    assert all(100 <= int(p) <= 199 for p in phones)


def test_dry_run_writes_results_and_resumes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runner, "RUNS", tmp_path)
    settings = Settings(_env_file=None)
    budget = Budget(tmp_path / "b.json", Limits(rpm=10**6, tpm=10**9, rpd=10**6))
    first = runner.run("t", RuleUnderstander(), settings, budget, limit=2)
    lines = first.read_text(encoding="utf-8").splitlines()
    assert [json.loads(x)["id"] for x in lines] == ["straightforward-01", "straightforward-02"]
    assert all(json.loads(x)["outcome"] == "done" for x in lines)
    runner.run("t", RuleUnderstander(), settings, budget, limit=1)  # resumes after the done ones
    ids = [json.loads(x)["id"] for x in first.read_text(encoding="utf-8").splitlines()]
    assert ids == ["straightforward-01", "straightforward-02", "straightforward-03"]


def test_committed_dataset_matches_the_generator() -> None:
    from evals.build_dataset import build

    assert [c.model_dump() for c in build()] == [c.model_dump() for c in load_cases()]


def test_system_text_replaces_user_values_with_a_placeholder() -> None:
    from evals.metrics import system_text

    values = {"Taylor Kowalski"}
    assert (
        system_text("Updated: full name is Taylor Kowalski.", values) == "Updated: full name is X."
    )
    assert system_text("Email address: a.b@example.com. Is that right?", set()) == (
        "Email address: X. Is that right?"
    )
    assert system_text("Updated: date of birth is May 14, 2004.", set()) == (
        "Updated: date of birth is X."
    )


def test_heldout_file_converts_without_changing_wording_and_plays(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from evals.heldout import convert

    source = Path(__file__).parent / "data" / "sample-heldout.md"
    case = convert(source)
    lines = [x[2:] for x in source.read_text(encoding="utf-8").splitlines() if x.startswith("- ")]
    assert list(case.script) == lines[: len(case.script)]  # the owner's words, unchanged
    assert case.expected["date_of_birth"].value == "1990-03-15"
    assert case.expected["inquiry_reason"].value == "something_else"
    assert case.expected["phone"].status == "skipped"

    dataset = tmp_path / "heldout.jsonl"
    dataset.write_text(json.dumps(case.model_dump(mode="json")) + "\n", encoding="utf-8")
    monkeypatch.setattr(runner, "RUNS", tmp_path)
    budget = Budget(tmp_path / "b.json", Limits(rpm=10**6, tpm=10**9, rpd=10**6))
    out = runner.run("h", RuleUnderstander(), Settings(_env_file=None), budget, dataset=dataset)
    result = json.loads(out.read_text(encoding="utf-8").splitlines()[0])
    assert (result["outcome"], result["submitted"]) == ("done", True)
    assert result["final"]["full_name"]["value"] == "Robin Hale"
    assert result["final"]["inquiry_reason"]["value"] == "something_else"


def test_gemma_limits_are_20_rpm_and_11k_tpm(tmp_path: Path) -> None:
    from evals.budget import MODEL_LIMITS

    gemma = MODEL_LIMITS["gemma-4-26b-a4b-it"]
    assert (gemma.rpm, gemma.tpm, gemma.rpd) == (20, 11_000, 11_520)
    t = FakeTime()
    budget = Budget(tmp_path / "g.json", gemma, clock=t.clock, sleep=t.sleep, today=lambda: "d")
    budget.after_turn(requests=2, tokens=5_500)  # tokens are hit first: 5 500 + 4 x 1 500 > 11K
    budget.before_turn()
    assert t.slept


def test_daily_counters_are_separate_per_api_project(tmp_path: Path) -> None:
    from evals.budget import quota_file

    one = quota_file(tmp_path, "default", "gemini-3.5-flash-lite")
    two = quota_file(tmp_path, "account2", "gemini-3.5-flash-lite")
    assert one != two
    Budget(one, Limits(), today=lambda: "d").after_turn(requests=300, tokens=0)
    assert Budget(two, Limits(), today=lambda: "d").used_today() == 0  # a different project
    assert "account2" in two.name  # a label, never a key


def test_quota_profile_is_a_plain_label() -> None:
    with pytest.raises(ValueError, match="eval_quota_profile"):
        Settings(_env_file=None, eval_quota_profile="AIza secret key!")
