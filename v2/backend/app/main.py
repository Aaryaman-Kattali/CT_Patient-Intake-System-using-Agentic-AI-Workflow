"""App factory. Run with: uv run uvicorn app.main:create_app --factory

Everything stateful (database engine, understander, services, rate limiters) is built once
in the lifespan and kept on `app.state`. There are no module-level globals (audit #5).
"""

import os
import sys
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import date

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agents.understanding_agent import build_understander
from app.api.errors import install_error_handlers
from app.api.routes import Services, router
from app.config import Settings, load_region_content
from app.domain import templates as t
from app.logging_setup import configure_logging
from app.runtime import warn_if_multiple_workers
from app.services.email import EmailProvider, EmailService, build_provider
from app.services.intake_service import IntakeService
from app.services.persistence import IntakeRepository, create_db_engine
from app.services.rate_limit import RESUME_WINDOW_S, FailureLimiter
from app.services.staff_outputs import StaffOutputs
from app.workflow.understanding import Understander


def _person_help(settings: Settings) -> tuple[str, ...]:
    lines = load_region_content(settings.region).needs_human.no_form
    return (*lines, t.DEMO_NO_CONTACT) if settings.synthetic_only else tuple(lines)


def create_app(
    settings: Settings | None = None,
    *,
    understander: Understander | None = None,
    email_provider: EmailProvider | None = None,
    today: Callable[[], date] = date.today,
) -> FastAPI:
    """`understander`, `email_provider` and `today` are injection points for tests."""
    settings = settings or Settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        warn_if_multiple_workers(sys.argv, os.environ)
        engine = create_db_engine(settings.database_url)
        repo = IntakeRepository(engine)
        agent = understander or build_understander(settings)  # built once per process
        intakes = IntakeService(repo, agent, settings, today=today)
        provider = email_provider or build_provider(
            settings.email_provider, settings.email_outbox_dir
        )
        window = RESUME_WINDOW_S
        app.state.services = Services(
            intakes=intakes,
            email=EmailService(repo, provider, synthetic=settings.synthetic_only),
            outputs=StaffOutputs(repo),
            code_failures=FailureLimiter(settings.resume_max_failures_per_code, window),
            client_failures=FailureLimiter(settings.resume_max_failures_per_client, window),
            person_help=_person_help(settings),
        )
        try:
            yield
        finally:
            close = getattr(agent, "close", None)
            if callable(close):
                close()
            engine.dispose()

    app = FastAPI(title="Intake assistant (demo, synthetic data only)", lifespan=lifespan)
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Intake-Token", "Idempotency-Key"],
    )
    install_error_handlers(app)
    app.include_router(router)

    @app.get("/health")
    def health() -> dict[str, str | bool]:
        return {"status": "ok", "synthetic_only": settings.synthetic_only}

    return app
