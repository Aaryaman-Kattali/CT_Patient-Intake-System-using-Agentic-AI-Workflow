"""Every error is a fixed code and message: never exception text or field values (audit B10)."""

from collections.abc import Iterator
from pathlib import Path
from typing import get_args

import pytest
from fastapi.testclient import TestClient

from app.api.errors import MESSAGES
from app.api.schemas import ErrorCode
from tests.api_helpers import Api, api_client
from tests.workflow_helpers import FI_SELF_BOOK

SECRETS = ("alex@example.com", "Alex Rivera", "202-555-0100", "C:/secret/path")


@pytest.fixture
def api(tmp_path: Path) -> Iterator[Api]:
    with api_client(tmp_path) as client:
        yield client


def test_every_error_code_has_one_fixed_message() -> None:
    assert set(MESSAGES) == set(get_args(ErrorCode))


def test_unexpected_exception_returns_fixed_error_without_details(
    api: Api, monkeypatch: pytest.MonkeyPatch
) -> None:
    tab = api.new_intake()

    def boom(*_: object) -> None:
        raise RuntimeError(" ".join(SECRETS))

    monkeypatch.setattr(api.client.app.state.services.intakes, "view", boom)  # type: ignore[attr-defined]
    # Like a real server: the error is answered, not raised into the test.
    client = TestClient(api.client.app, raise_server_exceptions=False)
    response = client.get(tab.url(), headers=tab.headers)
    assert response.status_code == 500
    assert response.json() == {
        "code": "internal_error",
        "message": "Something did not work on our side. Your saved answers are safe.",
        "view": None,
        "actions": [],
    }
    assert not [s for s in SECRETS if s in response.text]


def test_invalid_request_does_not_echo_input(api: Api) -> None:
    tab = api.new_intake()
    tab.run(FI_SELF_BOOK)
    body = {"turn": "not-a-number", "command": {"kind": "text", "text": "Alex Rivera"}}
    response = api.client.post(tab.url("/replies"), json=body, headers=tab.headers)
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_request"
    assert "Alex" not in response.text
    assert "not-a-number" not in response.text


@pytest.mark.parametrize(
    ("method", "path", "status", "code"),
    [
        ("GET", "/no-such-page", 404, "not_found"),
        ("DELETE", "/intakes", 405, "method_not_allowed"),
        ("GET", "/intakes/not-a-uuid", 422, "invalid_request"),
    ],
)
def test_framework_errors_use_the_same_shape(
    api: Api, method: str, path: str, status: int, code: str
) -> None:
    response = api.client.request(method, path)
    assert response.status_code == status
    assert response.json() == {"code": code, "message": MESSAGES[code], "view": None, "actions": []}  # type: ignore[index]
