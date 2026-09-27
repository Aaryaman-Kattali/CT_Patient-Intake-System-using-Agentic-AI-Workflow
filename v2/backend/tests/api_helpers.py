"""Drive the real FastAPI app (lifespan included) with a fake understander. No network."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi.testclient import TestClient
from httpx2 import Response

from app.config import Settings
from app.main import create_app
from app.services.email import Outgoing
from app.workflow.understanding import ReplyUnderstanding
from tests.workflow_helpers import TODAY, FakeUnderstander


class RecordingProvider:
    """Stands in for the email provider and records every message it is asked to send."""

    name = "recording"

    def __init__(self) -> None:
        self.sent: list[Outgoing] = []

    def send(self, message: Outgoing) -> None:
        self.sent.append(message)


@contextmanager
def api_client(
    tmp_path: Path,
    *,
    fake: FakeUnderstander | None = None,
    provider: RecordingProvider | None = None,
    **settings: Any,
) -> Iterator["Api"]:
    config = Settings(database_url=f"sqlite:///{(tmp_path / 'api.db').as_posix()}", **settings)
    fake = fake or FakeUnderstander()
    provider = provider or RecordingProvider()
    app = create_app(config, understander=fake, email_provider=provider, today=lambda: TODAY)
    with TestClient(app) as client:
        yield Api(client, fake, provider)


class Api:
    def __init__(self, client: TestClient, fake: FakeUnderstander, provider: RecordingProvider):
        self.client = client
        self.fake = fake
        self.provider = provider

    def new_intake(self) -> "Tab":
        response = self.client.post("/intakes")
        assert response.status_code == 201, response.text
        body = response.json()
        return Tab(self, UUID(body["id"]), body["token"], body["view"])


class Tab:
    """One browser tab: sends the turn number it last saw, and its token."""

    def __init__(self, api: Api, intake_id: UUID, token: str, view: dict[str, Any]) -> None:
        self.api = api
        self.id = intake_id
        self.token = token
        self.view = view

    @property
    def headers(self) -> dict[str, str]:
        return {"X-Intake-Token": self.token}

    def url(self, suffix: str = "") -> str:
        return f"/intakes/{self.id}{suffix}"

    def get(self, suffix: str = "") -> Response:
        return self.api.client.get(self.url(suffix), headers=self.headers)

    def post(
        self, suffix: str, body: dict[str, Any] | None = None, expect: int = 200, **kw: Any
    ) -> dict[str, Any]:
        headers = {**self.headers, **kw.pop("headers", {})}
        response = self.api.client.post(self.url(suffix), json=body, headers=headers, **kw)
        assert response.status_code == expect, (response.status_code, response.text)
        data: dict[str, Any] = response.json()
        if response.status_code == 200 and "state" in data:
            self.view = data
        elif isinstance(data.get("view"), dict):
            self.view = data["view"]
        return data

    def turn(self, suffix: str, expect: int = 200, **body: Any) -> dict[str, Any]:
        return self.post(suffix, {"turn": self.view["turn"], **body}, expect=expect)

    def reply(self, command: dict[str, Any], expect: int = 200) -> dict[str, Any]:
        return self.turn("/replies", expect=expect, command=command)

    def choose(self, option_id: str) -> dict[str, Any]:
        return self.reply({"kind": "choose", "option_id": option_id})

    def text(self, message: str, u: ReplyUnderstanding | None = None, expect: int = 200) -> Any:
        if u is not None:
            self.api.fake.queued.append(u)
        return self.reply({"kind": "text", "text": message}, expect=expect)

    def answer(self, value: str) -> dict[str, Any]:
        q = self.view["question"]
        if q["input_type"] == "choice" and q["kind"] == "field":
            return self.choose(value)
        answered: dict[str, Any] = self.text(value)
        return answered

    def run(self, book: dict[str, str]) -> dict[str, Any]:
        """Start and answer from the book until review; skip anything not in it."""
        if self.view["state"] == "greeting":
            self.turn("/start")
        for _ in range(60):
            q = self.view["question"]
            if q is None:
                break
            if q["kind"] != "field":
                self.choose("yes" if q["kind"].startswith("confirm") else q["options"][0]["id"])
            elif q["field_id"] in book:
                self.answer(book[q["field_id"]])
            else:
                self.reply({"kind": "skip"})
        assert self.view["state"] == "review", self.view["state"]
        return self.view

    def submit(self) -> dict[str, Any]:
        return self.turn("/submit")
