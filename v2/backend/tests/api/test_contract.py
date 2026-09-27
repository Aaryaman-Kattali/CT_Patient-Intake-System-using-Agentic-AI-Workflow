"""Contract: every endpoint's responses match the Pydantic models declared in OpenAPI.

The Phase 7 frontend generates its TypeScript types from the OpenAPI schema, so the schema
must describe exactly what the API sends: a success model per route and `ErrorBody` for
every error. This test records every response from a run that touches every endpoint
(success and error paths) and validates each one against the model its route declares.
"""

from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from pydantic import BaseModel
from starlette.routing import BaseRoute, Match

from app.api.schemas import ErrorBody
from tests.api_helpers import Api, api_client
from tests.workflow_helpers import FI_SELF_BOOK

Recorded = tuple[str, str, int, Any]


@pytest.fixture
def recorded(tmp_path: Path) -> Iterator[tuple[FastAPI, list[Recorded]]]:
    calls: list[Recorded] = []
    with api_client(tmp_path) as api:

        def record(response: httpx.Response) -> None:
            response.read()
            calls.append(
                (
                    response.request.method,
                    response.request.url.path,
                    response.status_code,
                    response.json(),
                )
            )

        api.client.event_hooks["response"].append(record)
        _touch_every_endpoint(api)
        yield api.client.app, calls  # type: ignore[misc]


def _touch_every_endpoint(api: Api) -> None:
    client = api.client
    tab = api.new_intake()
    tab.get()
    tab.post("/start", {"turn": 99}, expect=409)  # stale
    tab.reply({"kind": "skip"}, expect=409)  # not available before start
    tab.post("/resume-code", expect=409)  # not started yet
    tab.turn("/start")
    tab.post("/resume-code")
    tab.choose("family_inquiry")
    tab.choose("me")
    code = tab.turn("/pause")["resume_code"]
    tab.turn("/resume")
    tab.reply({"kind": "talk_to_person"})
    tab.turn("/resume")
    tab.get("/review")
    tab.post("/staff-summary", expect=409)
    tab.post("/benefit-summary", expect=409)
    tab.post("/email", expect=409, headers={"Idempotency-Key": "k"})
    tab.run(FI_SELF_BOOK)
    tab.post("/review/edit", {"turn": tab.view["turn"], "field_id": "gender"})
    tab.run(FI_SELF_BOOK)
    tab.submit()
    tab.post("/email", expect=400)  # no idempotency key
    tab.post("/email", headers={"Idempotency-Key": "k"})
    tab.post("/staff-summary")
    tab.post("/benefit-summary")
    client.post("/intakes/resume", json={"resume_code": code})
    client.post("/intakes/resume", json={"resume_code": "ABC-DEF"})
    client.post("/intakes/resume", json={"nope": 1})
    client.get("/intakes/00000000-0000-4000-8000-000000000000")
    client.get("/help/person")
    client.get("/ui/text")
    client.get("/no-such-page")


def api_routes(routes: Sequence[BaseRoute]) -> list[APIRoute]:
    """All APIRoutes, including those of included routers (FastAPI keeps them nested)."""
    found: list[APIRoute] = []
    for route in routes:
        if isinstance(route, APIRoute):
            found.append(route)
        elif (inner := getattr(route, "original_router", None)) is not None:
            found += api_routes(inner.routes)
    return found


def _route(app: FastAPI, method: str, path: str) -> APIRoute | None:
    scope = {"type": "http", "method": method, "path": path}
    routes = api_routes(app.routes)
    assert routes, "no API routes found"
    return next((r for r in routes if r.matches(scope)[0] is Match.FULL), None)


def _model(route: APIRoute | None, status: int) -> type[BaseModel]:
    if route is None or status >= 400:
        responses: dict[Any, Any] = route.responses if route else {}
        declared = responses.get(status, {}).get("model", ErrorBody)
        assert route is None or status in responses, (route.path, status, "not declared")
        return declared  # type: ignore[no-any-return]
    assert isinstance(route.response_model, type), route.path
    return route.response_model


def test_every_response_matches_its_declared_model(
    recorded: tuple[FastAPI, list[Recorded]],
) -> None:
    app, calls = recorded
    for method, path, status, body in calls:
        model = _model(_route(app, method, path), status)
        model.model_validate(body)  # raises if the response does not match the contract


def test_every_endpoint_was_exercised(recorded: tuple[FastAPI, list[Recorded]]) -> None:
    app, calls = recorded
    hit = {
        (route.path, method)
        for method, path, status, _ in calls
        if status < 300 and (route := _route(app, method, path)) is not None
    }
    endpoints = {
        (r.path, m) for r in api_routes(app.routes) if r.path != "/health" for m in r.methods or ()
    }
    assert len(endpoints) == 16
    assert endpoints - hit == set()


def test_openapi_declares_models_for_every_response(tmp_path: Path) -> None:
    with api_client(tmp_path) as api:
        schema = api.client.get("/openapi.json").json()
    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            for status, response in operation["responses"].items():
                content = response.get("content", {}).get("application/json", {})
                assert "schema" in content, (method, path, status)
    components = schema["components"]["schemas"]
    assert {
        "TurnView",
        "ErrorBody",
        "SessionView",
        "StaffSummary",
        "BenefitSummary",
        "ResumeCodeView",
    } <= set(components)
    question = components["TurnView"]["properties"]["question"]
    kinds = {option.get("type") for option in question["anyOf"]}
    assert "array" not in kinds  # one question object or null, never a list (P1)
