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
    synthetic_only: bool = True
    database_url: str = f"sqlite:///{DEFAULT_DB_PATH.as_posix()}"
    email_provider: Literal["console", "smtp"] = "console"
    region: str = Field(default="US", pattern=r"^[A-Z]{2}$")
    max_message_chars: int = Field(default=1000, ge=50, le=10_000)
    max_field_attempts: int = Field(default=3, ge=1, le=10)
    llm_timeout_s: float = Field(default=15.0, gt=0)
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

    @field_validator("region")
    @classmethod
    def _region_file_exists(cls, value: str) -> str:
        if not region_file(value).is_file():
            raise ValueError(f"No content file for REGION={value} in {REGIONS_DIR}")
        return value


class CrisisContent(BaseModel):
    heading: str
    lines: list[str] = Field(min_length=1)


class RegionContent(BaseModel):
    region: str
    crisis: CrisisContent


def region_file(region: str) -> Path:
    return REGIONS_DIR / f"{region.lower()}.toml"


@lru_cache
def load_region_content(region: str) -> RegionContent:
    """Load fixed, human-written region text. Crisis wording lives here, never in code."""
    with region_file(region).open("rb") as f:
        return RegionContent.model_validate(tomllib.load(f))
