# Intake assistant V2: backend

**Demo only. Synthetic data only.** Never enter real personal or health information. `SYNTHETIC_ONLY` cannot be turned off.

Spec: [`docs/V2_SPEC.md`](../../docs/V2_SPEC.md).

```bash
uv sync                      # install from uv.lock
uv run pytest                # tests (live LLM tests are skipped)
uv run pytest -m live        # live LLM tests only (needs an API key in .env)
uv run ruff check . && uv run ruff format --check . && uv run mypy
uv run uvicorn app.main:create_app --factory --reload
```

## API

`uv run uvicorn app.main:create_app --factory` serves the API on port 8000. The OpenAPI schema is at
`/openapi.json` (interactive docs at `/docs`); the frontend generates its types from it.
Endpoints, error codes and the `Turn` shape are in the spec (§9). Every `/intakes/{id}/*`
call needs the `X-Intake-Token` header returned by `POST /intakes`. No real email is ever sent:
the `console` provider logs one line, the `file` provider writes `.eml` files to
`~/.intake-v2/outbox`.

**Run a single process** (one uvicorn worker, the default). The resume-code rate limits are
kept in memory, so several workers would each keep their own counts. The app logs a warning
at startup if `--workers` or `WEB_CONCURRENCY` asks for more than one.

## Settings

Copy `.env.example` to `.env` in this folder. `.env` is gitignored.

- `APP_SECRET` (required, at least 32 characters). **Keep it the same.** Resume codes are
  derived from it, so if it changes, every resume code already given out stops working.
- `FRONTEND_ORIGIN` (default `http://localhost:5173`): the only origin allowed by CORS.
- `GOOGLE_API_KEY` (optional). Without it, buttons work and typed replies get
  "Typing is not working right now."
