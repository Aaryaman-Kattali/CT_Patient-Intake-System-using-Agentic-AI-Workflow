"""CORS: only the configured frontend origin may call the API from a browser."""

from pathlib import Path

from tests.api_helpers import api_client

ALLOWED = "http://localhost:5173"
OTHER = "http://intake.test"


def _preflight(tmp_path: Path, origin: str) -> dict[str, str]:
    with api_client(tmp_path, frontend_origin=ALLOWED) as api:
        response = api.client.options(
            "/intakes",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "X-Intake-Token",
            },
        )
        return dict(response.headers)


def test_frontend_origin_is_allowed(tmp_path: Path) -> None:
    headers = _preflight(tmp_path, ALLOWED)
    assert headers.get("access-control-allow-origin") == ALLOWED
    assert "x-intake-token" in headers.get("access-control-allow-headers", "").lower()


def test_other_origins_are_not_allowed(tmp_path: Path) -> None:
    headers = _preflight(tmp_path, OTHER)
    assert "access-control-allow-origin" not in headers


def test_simple_request_from_other_origin_gets_no_cors_header(tmp_path: Path) -> None:
    with api_client(tmp_path, frontend_origin=ALLOWED) as api:
        response = api.client.get("/health", headers={"Origin": OTHER})
        assert "access-control-allow-origin" not in response.headers
