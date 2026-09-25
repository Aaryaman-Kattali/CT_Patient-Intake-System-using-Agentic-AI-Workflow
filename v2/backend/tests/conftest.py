from pathlib import Path

import pytest

from app.config import Settings

# Env vars any Google SDK might read. Removed for every non-live test so a test
# that secretly needs a real key fails instead of silently calling the API.
API_KEY_VARS = ("GOOGLE_API_KEY", "GEMINI_API_KEY", "GOOGLE_GENAI_API_KEY")

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parents[1]


@pytest.fixture(autouse=True)
def _no_api_key(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    if request.node.get_closest_marker("live") is None:
        for var in API_KEY_VARS:
            monkeypatch.delenv(var, raising=False)


@pytest.fixture(autouse=True)
def _ignore_local_env_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings must not pick up a developer's local .env during tests."""
    monkeypatch.setitem(Settings.model_config, "env_file", None)
