"""The API must run as one process: warn when more than one worker is configured."""

import io
import logging

import pytest

from app.logging_setup import configure_logging
from app.runtime import configured_workers, warn_if_multiple_workers


@pytest.mark.parametrize(
    ("argv", "env", "workers"),
    [
        (["uvicorn", "app.main:create_app", "--factory"], {}, 1),
        (["uvicorn", "app.main:create_app", "--workers", "4"], {}, 4),
        (["uvicorn", "app.main:create_app", "--workers=2"], {}, 2),
        (["gunicorn", "-w", "3", "app.main:create_app()"], {}, 3),
        (["uvicorn", "app.main:create_app"], {"WEB_CONCURRENCY": "2"}, 2),
        (["uvicorn", "--workers", "nonsense"], {"WEB_CONCURRENCY": ""}, 1),
    ],
)
def test_configured_workers(argv: list[str], env: dict[str, str], workers: int) -> None:
    assert configured_workers(argv, env) == workers


def test_warning_logged_for_more_than_one_worker() -> None:
    stream = io.StringIO()
    configure_logging("INFO", stream)
    try:
        assert warn_if_multiple_workers(["uvicorn", "--workers", "2"], {})
        assert not warn_if_multiple_workers(["uvicorn"], {})
    finally:
        logging.getLogger().handlers.clear()
    assert stream.getvalue().count("run a single process") == 1
