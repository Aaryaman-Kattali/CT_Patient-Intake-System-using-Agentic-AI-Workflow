"""The app builds its understander and services once, in the lifespan; providers behave."""

import io
import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.agents.understanding_agent import NoKeyUnderstander
from app.config import Settings
from app.logging_setup import configure_logging
from app.services.email import ConsoleProvider, FileProvider, Outgoing
from app.workflow.understanding import AgentReply, UnderstandingContext
from tests.workflow_helpers import FakeUnderstander


def _settings(tmp_path: Path) -> Settings:
    return Settings(database_url=f"sqlite:///{(tmp_path / 'app.db').as_posix()}")


class ClosingFake(FakeUnderstander):
    closed = 0

    def close(self) -> None:
        ClosingFake.closed += 1

    def understand(self, message: str, context: UnderstandingContext) -> AgentReply:
        return super().understand(message, context)


def test_understander_built_once_and_closed_on_shutdown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    built: list[ClosingFake] = []

    def build(_: Settings) -> ClosingFake:
        built.append(ClosingFake())
        return built[-1]

    monkeypatch.setattr(main, "build_understander", build)
    app = main.create_app(_settings(tmp_path))
    assert built == []  # nothing is built at import or factory time
    with TestClient(app) as client:
        for _ in range(3):
            body = client.post("/intakes").json()
            headers = {"X-Intake-Token": body["token"]}
            client.post(f"/intakes/{body['id']}/start", json={"turn": 0}, headers=headers)
        assert len(built) == 1
    assert ClosingFake.closed == 1


def test_two_apps_have_independent_services(tmp_path: Path) -> None:
    first = main.create_app(_settings(tmp_path / "a"), understander=FakeUnderstander())
    second = main.create_app(_settings(tmp_path / "b"), understander=FakeUnderstander())
    with TestClient(first), TestClient(second):
        assert first.state.services is not second.state.services
        assert first.state.services.intakes is not second.state.services.intakes


def test_without_a_key_typing_reports_it_is_not_working(tmp_path: Path) -> None:
    app = main.create_app(_settings(tmp_path))
    with TestClient(app) as client:
        assert isinstance(app.state.services.intakes._understander, NoKeyUnderstander)
        body = client.post("/intakes").json()
        headers = {"X-Intake-Token": body["token"]}
        url = f"/intakes/{body['id']}"
        client.post(f"{url}/start", json={"turn": 0}, headers=headers)
        choose = {"kind": "choose", "option_id": "family_inquiry"}
        client.post(f"{url}/replies", json={"turn": 1, "command": choose}, headers=headers)
        choose = {"kind": "choose", "option_id": "me"}
        client.post(f"{url}/replies", json={"turn": 2, "command": choose}, headers=headers)
        typed = {"kind": "text", "text": "Alex Rivera"}
        view = client.post(f"{url}/replies", json={"turn": 3, "command": typed}, headers=headers)
        assert view.status_code == 200
        assert view.json()["info"][0] == "Typing is not working right now."


MESSAGE = Outgoing(to="alex@example.com", subject="s", body="b")


def test_file_provider_writes_to_the_outbox(tmp_path: Path) -> None:
    outbox = tmp_path / "outbox"
    FileProvider(outbox).send(MESSAGE)
    files = list(outbox.iterdir())
    assert len(files) == 1
    assert "alex@example.com" in files[0].read_text(encoding="utf-8")


def test_console_provider_never_logs_the_recipient() -> None:
    stream = io.StringIO()
    configure_logging("INFO", stream)
    try:
        ConsoleProvider().send(MESSAGE)
    finally:
        logging.getLogger().handlers.clear()
    assert "nothing was sent" in stream.getvalue()
    assert "alex" not in stream.getvalue()


def test_default_outbox_is_outside_the_repository() -> None:
    backend = Path(main.__file__).resolve().parents[1]
    outbox = Settings().email_outbox_dir.resolve()
    assert backend.parents[1] not in outbox.parents
