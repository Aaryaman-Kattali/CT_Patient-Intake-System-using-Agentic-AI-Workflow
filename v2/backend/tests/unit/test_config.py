import pytest
from pydantic import ValidationError

from app.config import Settings, load_region_content


def test_defaults_are_safe() -> None:
    s = Settings()
    assert s.synthetic_only is True
    assert s.email_provider == "console"
    assert s.region == "US"


def test_gemini_model_read_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_MODEL", "some-future-model")
    assert Settings().gemini_model == "some-future-model"


def test_unknown_region_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REGION", "ZZ")
    with pytest.raises(ValidationError, match="No content file"):
        Settings()


def test_region_must_be_two_letter_code(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REGION", "../us")
    with pytest.raises(ValidationError):
        Settings()


def test_settings_do_not_require_api_key() -> None:
    Settings()  # would raise if a key were mandatory; conftest removed all key vars


def test_us_region_content_has_crisis_lines() -> None:
    content = load_region_content("US")
    assert content.region == "US"
    assert any("911" in line for line in content.crisis.lines)
    assert any("988" in line for line in content.crisis.lines)
