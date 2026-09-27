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

## Settings

Copy `.env.example` to `.env` in this folder. `.env` is gitignored.

- `APP_SECRET` (required, at least 32 characters). **Keep it the same.** Resume codes are
  derived from it, so if it changes, every resume code already given out stops working.
- `GOOGLE_API_KEY` (optional). Without it, buttons work and typed replies get
  "Typing is not working right now."
