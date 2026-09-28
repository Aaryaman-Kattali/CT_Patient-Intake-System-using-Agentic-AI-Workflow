"""Application settings. The only place where model IDs and region defaults live."""

import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]
REGIONS_DIR = Path(__file__).resolve().parent / "content" / "regions"
# Outside the repository, so intake data can never be committed by accident.
DEFAULT_DB_PATH = Path.home() / ".intake-v2" / "intake.db"
DEFAULT_OUTBOX_DIR = Path.home() / ".intake-v2" / "outbox"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    gemini_model: str = Field(default="gemini-3.5-flash-lite", min_length=1)
    # Derives resume codes. Set in .env; at least 32 characters.
    app_secret: SecretStr = Field(min_length=32)
    # Read by our Settings from .env and passed to the Gemini client explicitly.
    # Optional: without it, buttons work and typed replies get "Typing is not working right now".
    google_api_key: SecretStr | None = None
    synthetic_only: bool = True
    database_url: str = f"sqlite:///{DEFAULT_DB_PATH.as_posix()}"
    # No real email is ever sent. "console" logs a redacted line; "file" writes .eml files.
    email_provider: Literal["console", "file"] = "console"
    email_outbox_dir: Path = DEFAULT_OUTBOX_DIR
    # The only origin the browser may call the API from (CORS).
    frontend_origin: str = "http://localhost:5173"
    # Failed resume-code attempts allowed per 15 minutes, per code and per client. The
    # window is fixed (RESUME_WINDOW_S) because the lockout message names it.
    resume_max_failures_per_code: int = Field(default=5, ge=1)
    resume_max_failures_per_client: int = Field(default=10, ge=1)
    # Eval only: a non-secret label for the API key's Google project, so each project keeps
    # its own daily request count. Never the key itself.
    eval_quota_profile: str = Field(default="default", pattern=r"^[a-z0-9_-]{1,32}$")
    region: str = Field(default="US", pattern=r"^[A-Z]{2}$")
    max_message_chars: int = Field(default=1000, ge=50, le=10_000)
    max_field_attempts: int = Field(default=3, ge=1, le=10)
    # One hedged call per turn (docs/V2_SPEC.md §6): nothing runs past the deadline.
    llm_deadline_s: float = Field(default=12.0, gt=0)
    llm_hedge_after_s: float = Field(default=4.0, gt=0)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    @field_validator("synthetic_only")
    @classmethod
    def _synthetic_only_is_mandatory(cls, value: bool) -> bool:
        if not value:
            raise ValueError(
                "SYNTHETIC_ONLY must be true. This demo has no real-data mode "
                "and must never process real personal or health information."
            )
        return value

    @field_validator("google_api_key")
    @classmethod
    def _blank_key_is_no_key(cls, value: SecretStr | None) -> SecretStr | None:
        return value if value is not None and value.get_secret_value().strip() else None

    @field_validator("region")
    @classmethod
    def _region_file_exists(cls, value: str) -> str:
        if not region_file(value).is_file():
            raise ValueError(f"No content file for REGION={value} in {REGIONS_DIR}")
        return value


class CrisisContent(BaseModel):
    heading: str
    lines: list[str] = Field(min_length=1)
    keywords: list[str] = Field(min_length=1)  # checked before any LLM call


class NeedsHumanContent(BaseModel):
    """What happens after "Talk to a person", in a real clinic (region-specific)."""

    with_contact: list[str] = Field(min_length=1)
    without_contact: list[str] = Field(min_length=1)
    no_form: list[str] = Field(min_length=1)  # e.g. locked out of a resume code


class RegionContent(BaseModel):
    region: str
    crisis: CrisisContent
    needs_human: NeedsHumanContent


def region_file(region: str) -> Path:
    return REGIONS_DIR / f"{region.lower()}.toml"


@lru_cache
def load_region_content(region: str) -> RegionContent:
    """Load fixed, human-written region text. Crisis wording lives here, never in code."""
    with region_file(region).open("rb") as f:
        return RegionContent.model_validate(tomllib.load(f))
