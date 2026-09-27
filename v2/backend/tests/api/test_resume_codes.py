"""Resume with a code on a new device: one fixed failure message, rate-limited (spec §8)."""

from pathlib import Path
from typing import Any

import httpx2

from app.services.rate_limit import FailureLimiter
from tests.api_helpers import Api, Tab, api_client

FAILED = {
    "code": "resume_failed",
    "message": "That code did not work. Please check it and try again.",
    "view": None,
}
LIMITED = {
    "code": "too_many_attempts",
    "message": "Too many tries. Please wait a few minutes and try again.",
    "view": None,
}
WRONG_CODE = "ABC-DEF"  # valid shape, no such intake


def _paused(api: Api) -> tuple[Tab, str]:
    tab = api.new_intake()
    tab.turn("/start")
    tab.choose("family_inquiry")
    code: str = tab.turn("/pause")["resume_code"]
    return tab, code


def _resume(api: Api, code: str) -> httpx2.Response:
    return api.client.post("/intakes/resume", json={"resume_code": code})


def _json(response: httpx2.Response) -> dict[str, Any]:
    body: dict[str, Any] = response.json()
    return body


def test_resume_code_opens_intake_on_a_new_device(tmp_path: Path) -> None:
    with api_client(tmp_path) as api:
        tab, code = _paused(api)
        typed = code.lower().replace("-", " ")  # any case, spaces or dashes
        response = _resume(api, typed)
        assert response.status_code == 200
        body = _json(response)
        assert body["id"] == str(tab.id)
        assert body["view"]["state"] == "choose_intake_type" or body["view"]["question"]
        assert body["view"]["state"] != "paused"  # resumed where they were
        new = api.client.get(tab.url(), headers={"X-Intake-Token": body["token"]})
        assert new.status_code == 200
        old = api.client.get(tab.url(), headers=tab.headers)
        assert old.status_code == 404  # the old token stops working


def test_failed_attempts_get_one_fixed_message(tmp_path: Path) -> None:
    with api_client(tmp_path) as api:
        _paused(api)
        answers = [_resume(api, code) for code in (WRONG_CODE, "hello", "")]
        assert {r.status_code for r in answers} == {400}
        assert all(_json(r) == FAILED for r in answers)  # nothing tells if a code exists


def test_code_before_first_pause_does_not_work(tmp_path: Path) -> None:
    with api_client(tmp_path) as api:
        tab = api.new_intake()
        code = api.client.app.state.services.intakes.resume_code(tab.id)  # type: ignore[attr-defined]
        assert _json(_resume(api, code)) == FAILED


def test_rate_limited_per_code(tmp_path: Path) -> None:
    with api_client(tmp_path, resume_max_failures_per_code=3) as api:
        for _ in range(3):
            assert _json(_resume(api, WRONG_CODE)) == FAILED
        assert _resume(api, WRONG_CODE.lower()).status_code == 429  # same code, any spelling
        assert _json(_resume(api, "ABC-DEG")) == FAILED  # other codes are not blocked


def test_rate_limited_per_client_even_for_a_correct_code(tmp_path: Path) -> None:
    with api_client(tmp_path, resume_max_failures_per_client=3) as api:
        _, code = _paused(api)
        for wrong in ("ABC-DEF", "ABC-DEG", "ABC-DEH"):
            _resume(api, wrong)
        response = _resume(api, code)
        assert response.status_code == 429
        assert _json(response) == LIMITED


def test_failure_window_expires() -> None:
    now = [0.0]
    limiter = FailureLimiter(max_failures=2, window_s=60, clock=lambda: now[0])
    limiter.record_failure("k")
    limiter.record_failure("k")
    assert limiter.blocked("k")
    now[0] = 61.0
    assert not limiter.blocked("k")
    assert limiter._failures == {}  # expired keys are dropped
