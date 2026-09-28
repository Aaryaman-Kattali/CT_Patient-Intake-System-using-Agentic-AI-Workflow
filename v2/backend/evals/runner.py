"""Run the eval cases through the real V2 service (docs/V2_SPEC.md §14).

    uv run python -m evals.runner --run v2-live             # real Gemini, throttled
    uv run python -m evals.runner --run dry --dry-run       # rule-based fake, no API calls

Results go to ~/.intake-v2/evals/<run>/ (outside the repository): one JSON line per finished
case in results.jsonl. A stopped run resumes from the first case without a result.

The runner plays the user the way the real UI works: choice questions are buttons, text
questions are typed. It confirms a yes/no only when the value is what the case expects (a user
confirms correct values), picks the expected date, and resolves conflicts as the case says.
"""

import argparse
import json
import logging
import random
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from app.agents.understanding_agent import build_understander
from app.config import Settings
from app.domain import templates as t
from app.domain.fields import FieldState
from app.services.intake_service import IntakeService, TurnResult
from app.services.persistence import IntakeRepository, create_db_engine
from app.workflow import commands as c
from app.workflow.metrics import repeated_questions
from app.workflow.states import State
from app.workflow.understanding import Understander
from app.workflow.view import TurnView
from evals.budget import MODEL_LIMITS, Budget, DailyLimitReached, Limits, quota_file
from evals.cases import Case, Special, load_cases
from evals.common import norm, say

log = logging.getLogger("evals.runner")
RUNS = Path.home() / ".intake-v2" / "evals"
API_FAILURES = ("llm_timeout", "llm_error", "llm_no_key")  # not the model's fault
MAX_STEPS = 120
# Buttons a held-out script can press besides the answer options.
ACTION_COMMANDS: dict[str, c.Command] = {
    "start": c.Start(),
    "resume": c.Resume(),
    "continue_alone": c.ContinueAlone(),
    "take_a_break": c.Pause(),
    "keep_going": c.KeepGoing(),
    "talk_to_a_person": c.TalkToPerson(),
    "undo": c.Undo(),
    "answer_later": c.Skip(),
    "submit": c.Submit(),
}
BAR_LABELS = {t.BUTTONS["skip"].casefold(), t.BUTTONS["answer_later"].casefold()}
BACKOFF_S = (5.0, 15.0, 45.0)


def texts_of(view: TurnView) -> list[str]:
    q = view.question
    value = q.value if q else None  # the value box under a checking question
    return [x for x in (view.acknowledgement, *view.info, q.text if q else None, value) if x]


class CaseRun:
    """One case, played turn by turn."""

    def __init__(self, service: IntakeService, budget: Budget, case: Case) -> None:
        self.s, self.budget, self.case = service, budget, case
        self.repo: IntakeRepository = service._repo  # the eval reads its own run's database
        created = service.create()
        self.id: UUID = created.intake_id
        self.view = created.view
        self.used: set[int] = set()  # specials already used
        self.sends: dict[str, int] = {}  # book answers sent per field
        self.turns: list[dict[str, Any]] = []
        self.specials: list[dict[str, Any]] = []
        self.confirmations: list[dict[str, str]] = []
        self.conflicts: list[dict[str, str]] = []
        self.api_failures = 0
        self.outcome = "done"
        self.submit_tries = 0
        self.script_pos = 0  # held-out cases: the next scripted turn

    # --- the loop ----------------------------------------------------------------------

    def run(self) -> dict[str, Any]:
        if not self.case.script:  # a held-out script presses Start itself
            self._send(c.Start(), "button", None)
        for _ in range(MAX_STEPS):
            if self.view.state is State.SUBMITTED or self.outcome != "done":
                break
            if not self._step():
                break
        else:
            self.outcome = "too_many_steps"
        return self._result()

    def _step(self) -> bool:
        if self.case.script:
            return self._scripted()
        v = self.view
        if v.state is State.PAUSED:  # come back with the code, as on another device
            opened = self.s.open_with_resume_code(v.resume_code or "")
            if opened is None:
                self.outcome = "resume_failed"
                return False
            self.view = opened.view
            self._log("resume_code", None, None, None, self.view)
            return True
        if v.state is State.NEEDS_HUMAN:
            return self._send(c.ContinueAlone(), "button", None)
        if v.state is State.REVIEW:
            return self._review()
        if v.question is None:
            if any(a.id == "keep_going" for a in v.actions):
                return self._send(c.KeepGoing(), "button", None)
            self.outcome = "no_question"
            return False
        q = v.question
        if q.kind == "field":
            return self._field(q.field_id, q.can_skip or q.can_defer)
        return self._queue(q.kind, q.field_id, [o.id for o in q.options])

    def _scripted(self) -> bool:
        """Held-out case: play the owner's next turn, exactly as written."""
        v = self.view
        if self.script_pos >= len(self.case.script):
            if v.state is State.REVIEW and self.submit_tries == 0:
                self.submit_tries += 1
                return self._send(c.Submit(), "button", None)
            self.outcome = "done" if v.state is State.SUBMITTED else "script_ended"
            return False
        turn = self.case.script[self.script_pos]
        self.script_pos += 1
        field = v.question.field_id if v.question else None
        if not turn.startswith("[button]"):
            return self._send(c.Text(text=turn), "typed", field)
        command = self._button(turn[len("[button]") :].strip())
        if command is None:
            self.outcome = f"unknown_button:{turn}"
            return False
        return self._send(command, "button", field)

    def _button(self, label: str) -> c.Command | None:
        """The button with these words on the current screen, as the UI shows it."""
        q = self.view.question
        for option in q.options if q else ():
            if option.free_text and label.casefold().startswith(option.label.casefold() + ":"):
                typed = label[len(option.label) + 1 :].strip()
                return c.Choose(option_id=option.id, extra_text=typed)
            if option.label.casefold() == label.casefold():
                return c.Choose(option_id=option.id)
        for action in self.view.actions:
            if action.label.casefold() == label.casefold() and action.id in ACTION_COMMANDS:
                return ACTION_COMMANDS[action.id]
        if q and q.kind == "field" and label.casefold() in BAR_LABELS:
            return c.Skip()
        return None

    def _field(self, field: str, skippable: bool) -> bool:
        special = next(
            (i for i, s in enumerate(self.case.specials) if s.at == field and i not in self.used),
            None,
        )
        if special is not None:
            self.used.add(special)
            return self._special(self.case.specials[special])
        answer = self.case.book.get(field)
        sent = self.sends.get(field, 0)
        self.sends[field] = sent + 1
        if answer is None or answer.skip or (answer.say and sent >= 2):
            if not skippable:
                self.outcome = f"cannot_answer:{field}"
                return False
            return self._send(c.Skip(), "button", field)
        if answer.press:
            return self._send(
                c.Choose(option_id=answer.press, extra_text=answer.extra_text), "button", field
            )
        text = answer.say if sent == 0 else (answer.retry or answer.say)
        kinds = answer.kinds if sent == 0 else ("answer",)
        return self._send(c.Text(text=text or ""), "typed", field, kinds)

    def _special(self, sp: Special) -> bool:
        before = self._answers()
        if sp.action == "pause":
            ok = self._send(c.Pause(), "button", sp.at)
        elif sp.action == "talk_to_person":
            ok = self._send(c.TalkToPerson(), "button", sp.at)
        else:
            ok = self._send(c.Text(text=sp.say or ""), "special", sp.at, sp.kinds)
        shown = " ".join(texts_of(self.view))
        after = self._answers()
        self.specials.append(
            {
                "at": sp.at,
                "kinds": list(sp.kinds),
                "reply_kind": self.turns[-1].get("reply_kind") if self.turns else None,
                "must_show": {text: text in shown for text in sp.must_show},
                "state_after": self.view.state.value,
                "newly_skipped": [
                    f
                    for f, st in after.items()
                    if st.status.value in ("skipped", "deferred", "dont_know")
                    and (f not in before or before[f].status != st.status)
                ],
                "forbidden": list(sp.forbidden),
                "injection": self.case.category == "injection",
            }
        )
        return ok

    def _queue(self, kind: str, field: str, options: list[str]) -> bool:
        snap = self.repo.load(self.id)
        if snap is None or not snap.queue:
            raise RuntimeError("a yes/no question is shown but the queue is empty")
        item = snap.queue[0]
        expected = self.case.expected.get(field)
        want = norm(expected.value) if expected else None
        if kind in ("confirm_extra", "confirm_value", "confirm_change"):
            yes = want is not None and norm(item.value) == want
            self.confirmations.append(
                {"field": field, "kind": kind, "answer": "yes" if yes else "no"}
            )
            return self._send(c.Choose(option_id="yes" if yes else "no"), "button", field)
        if kind == "date_choice":
            pick = next((o for o in options if norm(o) == want), options[0])
            self.confirmations.append({"field": field, "kind": kind, "answer": pick})
            return self._send(c.Choose(option_id=pick), "button", field)
        choice: str | None = self.case.conflict_choice.get(field)
        if choice is None:
            current = snap.answers.get(field)
            choice = (
                "new"
                if norm(item.value) == want
                else "old"
                if current and norm(current.value) == want
                else "neither"
            )
        self.conflicts.append({"field": field, "choice": choice})
        return self._send(c.Choose(option_id=choice), "button", field)

    def _review(self) -> bool:
        review = self.view.review
        missing = {m.field_id for m in review.missing} if review else set()
        for field in self.case.mark_unknown:
            current = self._answers().get(field)
            if field in missing and (
                current is None or current.status.value != "unknown_confirmed"
            ):
                return self._send(c.MarkUnknown(field_id=field), "button", field)
        if not self.case.complete or self.submit_tries > 0:
            self.outcome = "not_submitted" if self.case.complete else "done"
            return False
        self.submit_tries += 1
        return self._send(c.Submit(), "button", None)

    # --- sending ---------------------------------------------------------------------

    def _send(
        self, command: c.Command, how: str, field: str | None, kinds: tuple[str, ...] = ()
    ) -> bool:
        typed = isinstance(command, c.Text)
        for attempt in range(len(BACKOFF_S) + 1):
            if typed:
                self.budget.before_turn()
            calls_before = len(self.repo.llm_calls(self.id))
            started = time.monotonic()
            result = self.s.handle(self.id, self.view.turn, command)
            calls = self.repo.llm_calls(self.id)[calls_before:]
            requests = sum(max(row.attempts, 1) for row in calls if row.status != "no_key")
            tokens = sum((row.input_tokens or 0) + (row.output_tokens or 0) for row in calls)
            self.budget.after_turn(requests, tokens)
            if result.status == "rejected" and result.reason in API_FAILURES:
                self.api_failures += 1
                self._log(how, field, command, kinds, result.view, calls, api_failure=True)
                if attempt < len(BACKOFF_S):
                    time.sleep(BACKOFF_S[attempt] * random.uniform(1.0, 1.5))  # noqa: S311
                    continue
                self.outcome = "api_failed"
                return False
            return self._after(
                result, how, field, command, kinds, calls, time.monotonic() - started
            )
        return False

    def _after(
        self,
        result: TurnResult,
        how: str,
        field: str | None,
        command: c.Command,
        kinds: tuple[str, ...],
        calls: list[Any],
        seconds: float,
    ) -> bool:
        if result.view is None:
            self.outcome = f"no_view:{result.status}"
            return False
        self._log(
            how,
            field,
            command,
            kinds,
            result.view,
            calls,
            seconds=seconds,
            rejected=result.reason if result.status != "applied" else None,
        )
        if result.status == "stale":
            self.outcome = "stale"
            return False
        self.view = result.view
        return True

    def _log(
        self,
        how: str,
        field: str | None,
        command: c.Command | None,
        kinds: tuple[str, ...] | None,
        view: TurnView | None,
        calls: list[Any] = (),  # type: ignore[assignment]
        api_failure: bool = False,
        seconds: float = 0.0,
        rejected: str | None = None,
    ) -> None:
        texts = texts_of(view) if view else []
        self.turns.append(
            {
                "how": how,
                "field": field,
                "command": command.kind if command else None,
                "expected_kinds": list(kinds or ()),
                "reply_kind": calls[-1].reply_kind if calls else None,
                "llm_status": calls[-1].status if calls else None,
                "api_failure": api_failure,
                "rejected": rejected,
                "seconds": round(seconds, 3),
                "state": view.state.value if view else None,
                "question": (view.question.kind, view.question.field_id)
                if view and view.question
                else None,
                "question_text": view.question.text if view and view.question else None,
                "question_marks": sum(x.count("?") for x in texts),
                "texts": texts,
            }
        )

    def _answers(self) -> dict[str, FieldState]:
        snap = self.repo.load(self.id)
        return dict(snap.answers) if snap else {}

    def _result(self) -> dict[str, Any]:
        snap = self.repo.load(self.id)
        events = self.repo.events(self.id)
        calls = self.repo.llm_calls(self.id)
        return {
            "id": self.case.id,
            "category": self.case.category,
            "persona": self.case.persona,
            "intake": self.case.intake,
            "outcome": self.outcome,
            "submitted": bool(snap and snap.state is State.SUBMITTED),
            "final": {
                f: {
                    "status": st.status.value,
                    "value": st.value,
                    "display": st.display,
                    "unresolved_other": st.unresolved_other,
                    "source": st.source.value if st.source else None,
                }
                for f, st in (snap.answers.items() if snap else [])
            },
            "turns": self.turns,
            "specials": self.specials,
            "confirmations": self.confirmations,
            "conflicts": self.conflicts,
            "repeated_questions": repeated_questions(events),
            "submitted_events": sum(e.type == "submitted" for e in events),
            "email_events": sum(e.type.startswith("email_sent") for e in events),
            "api_failures": self.api_failures,
            "llm_calls": [
                row.model_dump(
                    include={
                        "status",
                        "reply_kind",
                        "attempts",
                        "hedged",
                        "winner",
                        "hedge_suppressed",
                        "error_class",
                        "latency_ms",
                        "input_tokens",
                        "output_tokens",
                    }
                )
                for row in calls
            ],
        }


def run(
    run_name: str,
    understander: Understander,
    settings: Settings,
    budget: Budget,
    only: set[str] | None = None,
    limit: int | None = None,
    dataset: Path | None = None,
) -> Path:
    folder = RUNS / run_name
    folder.mkdir(parents=True, exist_ok=True)
    results = folder / "results.jsonl"
    done = set()
    if results.exists():
        done = {
            json.loads(line)["id"]
            for line in results.read_text(encoding="utf-8").splitlines()
            if line
        }
    repo = IntakeRepository(create_db_engine(f"sqlite:///{(folder / 'intake.db').as_posix()}"))
    service = IntakeService(repo, understander, settings)
    all_cases = load_cases(dataset) if dataset else load_cases()
    cases = [c for c in all_cases if (not only or c.id in only) and c.id not in done]
    for case in cases[:limit]:
        started = time.monotonic()
        try:
            result = CaseRun(service, budget, case).run()
        except DailyLimitReached as stop:
            log.warning("daily request limit reached, stopping cleanly: %s", stop)
            say(f"Stopped before {case.id}: {stop}. Run again tomorrow to resume.")
            break
        result["duration_s"] = round(time.monotonic() - started, 1)
        with results.open("a", encoding="utf-8") as f:
            f.write(json.dumps(result) + "\n")
        say(
            f"{case.id}: {result['outcome']} ({result['duration_s']} s, "
            f"{budget.used_today()} requests today)"
        )
    return results


def _write_meta(folder: Path, settings: Settings, profile: str, note: str | None) -> None:
    """Run metadata: labels only. Never the API key."""
    meta = folder / "run_meta.json"
    if meta.exists():
        return  # a resumed run keeps its first metadata
    commit = subprocess.run(
        ["git", "-c", "safe.directory=*", "rev-parse", "--short", "HEAD"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
        cwd=Path(__file__).parent,
    ).stdout.strip()
    dataset = load_cases()
    meta.write_text(
        json.dumps(
            {
                "model": settings.gemini_model,
                "quota_profile": profile,
                "git_commit": commit,
                "cases": len(dataset),
                "started_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "llm_deadline_s": settings.llm_deadline_s,
                "llm_hedge_after_s": settings.llm_hedge_after_s,
                "note": note,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    parser.add_argument("--dry-run", action="store_true", help="rule-based fake, no API calls")
    parser.add_argument("--only", nargs="*")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dataset", type=Path, help="default: the 61 scripted cases")
    parser.add_argument("--model", help="override GEMINI_MODEL (e.g. gemma-4-26b-a4b-it)")
    parser.add_argument("--quota-profile", help="override EVAL_QUOTA_PROFILE (a label)")
    parser.add_argument("--note", help="free text for run_meta.json (no secrets)")
    args = parser.parse_args()
    if args.dry_run:
        from tests.e2e_server import RuleUnderstander

        settings = Settings(_env_file=None)
        understander: Understander = RuleUnderstander()
        limits = Limits(rpm=10**6, tpm=10**9, rpd=10**6)
    else:
        settings = Settings(gemini_model=args.model) if args.model else Settings()
        understander = build_understander(settings)
        limits = MODEL_LIMITS[settings.gemini_model]
    # Live runs share one daily count per model (V2 and the V1 baseline use the same key
    # and model); another model (Gemma) has its own quota and its own count.
    profile = args.quota_profile or settings.eval_quota_profile
    quota = (
        RUNS / args.run / "budget.json"
        if args.dry_run
        else quota_file(RUNS, profile, settings.gemini_model)
    )
    _write_meta(RUNS / args.run, settings, profile, args.note)
    budget = Budget(quota, limits)
    path = run(
        args.run, understander, settings, budget, set(args.only or ()), args.limit, args.dataset
    )
    say(f"Results: {path}")


if __name__ == "__main__":
    main()
