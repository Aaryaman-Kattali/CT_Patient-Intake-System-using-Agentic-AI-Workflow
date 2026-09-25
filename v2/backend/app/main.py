"""App factory. Run with: uv run uvicorn app.main:create_app --factory"""

from fastapi import FastAPI

from app.config import Settings
from app.logging_setup import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    configure_logging(settings.log_level)

    app = FastAPI(title="Intake assistant (demo, synthetic data only)")
    app.state.settings = settings

    @app.get("/health")
    def health() -> dict[str, str | bool]:
        return {"status": "ok", "synthetic_only": settings.synthetic_only}

    return app
