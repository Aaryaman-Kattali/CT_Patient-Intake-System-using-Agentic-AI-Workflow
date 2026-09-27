"""HTTP endpoints (docs/V2_SPEC.md §9.1). Thin: every decision is made by the services.

All /intakes/{id}/* routes need the X-Intake-Token header (a demo token, not an auth system).
A wrong token and an unknown id get the same answer, so ids cannot be probed.
"""

from dataclasses import dataclass
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request

from app.api.errors import ApiError
from app.api.schemas import (
    EditRequest,
    EmailRequest,
    ErrorBody,
    HelpView,
    ReplyRequest,
    ResumeCodeRequest,
    ResumeCodeView,
    SessionView,
    TurnRequest,
    UiText,
)
from app.domain import templates as t
from app.services.benefit_summary import BenefitSummary
from app.services.email import EmailService, EmailStatus
from app.services.intake_service import IntakeService, TurnResult
from app.services.rate_limit import FailureLimiter
from app.services.resume_codes import normalize
from app.services.staff_outputs import StaffOutputs
from app.services.staff_summary import StaffSummary
from app.workflow import commands as c
from app.workflow.states import State
from app.workflow.view import TurnView


@dataclass(frozen=True)
class Services:
    intakes: IntakeService
    email: EmailService
    outputs: StaffOutputs
    code_failures: FailureLimiter
    client_failures: FailureLimiter
    person_help: tuple[str, ...]  # "Talk to a person" with no form open


def _errors(*statuses: int) -> dict[int | str, dict[str, Any]]:
    return {status: {"model": ErrorBody} for status in (*statuses, 422, 500)}


router = APIRouter()


def services(request: Request) -> Services:
    found: Services = request.app.state.services
    return found


ServicesDep = Annotated[Services, Depends(services)]


def intake_id_with_token(
    intake_id: UUID,
    svc: ServicesDep,
    x_intake_token: Annotated[str | None, Header(max_length=128)] = None,
) -> UUID:
    if not x_intake_token or not svc.intakes.verify_token(intake_id, x_intake_token):
        raise ApiError(404, "intake_not_found")
    return intake_id


IntakeId = Annotated[UUID, Depends(intake_id_with_token)]


# --- create, read, resume --------------------------------------------------------------


@router.post("/intakes", status_code=201, response_model=SessionView, responses=_errors())
def create_intake(svc: ServicesDep) -> SessionView:
    created = svc.intakes.create()
    return SessionView(id=created.intake_id, token=created.token, view=created.view)


@router.get("/intakes/{intake_id}", response_model=TurnView, responses=_errors(404))
def get_intake(intake_id: IntakeId, svc: ServicesDep) -> TurnView:
    return _found(svc.intakes.view(intake_id))


@router.post("/intakes/resume", response_model=SessionView, responses=_errors(400, 429))
def resume_with_code(body: ResumeCodeRequest, request: Request, svc: ServicesDep) -> SessionView:
    """Open an intake on a new device. Failures get one fixed answer, whether or not the
    code exists, and are rate-limited per code and per client."""
    code_key = normalize(body.resume_code) or body.resume_code.strip().casefold()
    client_key = request.client.host if request.client else "unknown"
    if svc.code_failures.blocked(code_key) or svc.client_failures.blocked(client_key):
        raise ApiError(429, "too_many_attempts")
    opened = svc.intakes.open_with_resume_code(body.resume_code)
    if opened is None:
        svc.code_failures.record_failure(code_key)
        svc.client_failures.record_failure(client_key)
        raise ApiError(400, "resume_failed")
    return SessionView(id=opened.intake_id, token=opened.token, view=opened.view)


@router.post(
    "/intakes/{intake_id}/resume-code", response_model=ResumeCodeView, responses=_errors(404, 409)
)
def resume_code(intake_id: IntakeId, svc: ServicesDep) -> ResumeCodeView:
    """The resume code on request, any time after starting ("Take a break" area)."""
    code = svc.intakes.resume_code_on_request(intake_id)
    if code is None:
        raise ApiError(409, "action_not_available")
    return ResumeCodeView(resume_code=code, info=t.RESUME_CODE_INFO)


@router.get("/help/person", response_model=HelpView, responses=_errors())
def person_help(svc: ServicesDep) -> HelpView:
    """What to do to talk to a person when no form is open (e.g. after a lockout)."""
    return HelpView(info=svc.person_help)


@router.get("/ui/text", response_model=UiText, responses=_errors())
def ui_text() -> UiText:
    """Fixed interface wording, so the frontend writes none of its own."""
    return UiText(buttons=dict(t.BUTTONS), labels=dict(t.UI_LABELS), sentences=dict(t.UI_SENTENCES))


# --- turns --------------------------------------------------------------------------------


@router.post("/intakes/{intake_id}/start", response_model=TurnView, responses=_errors(404, 409))
def start(intake_id: IntakeId, body: TurnRequest, svc: ServicesDep) -> TurnView:
    return _turn(svc.intakes.handle(intake_id, body.turn, c.Start()))


@router.post("/intakes/{intake_id}/replies", response_model=TurnView, responses=_errors(404, 409))
def reply(intake_id: IntakeId, body: ReplyRequest, svc: ServicesDep) -> TurnView:
    return _turn(svc.intakes.handle(intake_id, body.turn, body.command))


@router.post("/intakes/{intake_id}/pause", response_model=TurnView, responses=_errors(404, 409))
def pause(intake_id: IntakeId, body: TurnRequest, svc: ServicesDep) -> TurnView:
    return _turn(svc.intakes.handle(intake_id, body.turn, c.Pause()))


@router.post("/intakes/{intake_id}/resume", response_model=TurnView, responses=_errors(404, 409))
def resume(intake_id: IntakeId, body: TurnRequest, svc: ServicesDep) -> TurnView:
    """PAUSED -> where the user was. NEEDS_HUMAN -> "Continue on my own"."""
    current = _found(svc.intakes.view(intake_id))
    command = c.ContinueAlone() if current.state is State.NEEDS_HUMAN else c.Resume()
    return _turn(svc.intakes.handle(intake_id, body.turn, command))


@router.get("/intakes/{intake_id}/review", response_model=TurnView, responses=_errors(404))
def review(intake_id: IntakeId, svc: ServicesDep) -> TurnView:
    return _found(svc.intakes.review(intake_id))


@router.post(
    "/intakes/{intake_id}/review/edit", response_model=TurnView, responses=_errors(404, 409)
)
def review_edit(intake_id: IntakeId, body: EditRequest, svc: ServicesDep) -> TurnView:
    return _turn(svc.intakes.handle(intake_id, body.turn, c.EditField(field_id=body.field_id)))


@router.post("/intakes/{intake_id}/submit", response_model=TurnView, responses=_errors(404, 409))
def submit(intake_id: IntakeId, body: TurnRequest, svc: ServicesDep) -> TurnView:
    view = _turn(svc.intakes.handle(intake_id, body.turn, c.Submit()))
    if view.state is not State.SUBMITTED:
        raise ApiError(409, "form_incomplete", view)
    return view


# --- side effects (SUBMITTED only) ---------------------------------------------------------

_EMAIL_ERRORS: dict[EmailStatus, tuple[int, Any]] = {
    "not_submitted": (409, "email_not_submitted"),
    "no_email": (409, "email_no_address"),
    "not_synthetic": (409, "email_not_synthetic"),
    "failed": (502, "email_failed"),
    "sending": (409, "action_not_available"),
}


@router.post(
    "/intakes/{intake_id}/email", response_model=TurnView, responses=_errors(400, 404, 409, 502)
)
def send_email(
    intake_id: IntakeId,
    svc: ServicesDep,
    idempotency_key: Annotated[str | None, Header(max_length=128)] = None,
    body: EmailRequest | None = None,
) -> TurnView:
    """No recipient anywhere in this request: it is read from the stored email field."""
    if not idempotency_key:
        raise ApiError(400, "idempotency_key_required")
    result = svc.email.send_confirmation(intake_id, idempotency_key)
    if result.status != "sent":
        status, code = _EMAIL_ERRORS[result.status]
        raise ApiError(status, code)
    snap_view = _found(svc.intakes.view(intake_id))
    return snap_view.model_copy(update={"info": (*snap_view.info, t.EMAIL_SENT)})


@router.post(
    "/intakes/{intake_id}/staff-summary", response_model=StaffSummary, responses=_errors(404, 409)
)
def staff_summary(intake_id: IntakeId, svc: ServicesDep) -> StaffSummary:
    result = svc.outputs.staff_summary(intake_id)
    if isinstance(result, str):
        raise _output_error(result)
    return result


@router.post(
    "/intakes/{intake_id}/benefit-summary",
    response_model=BenefitSummary,
    responses=_errors(404, 409),
)
def benefit_summary(intake_id: IntakeId, svc: ServicesDep) -> BenefitSummary:
    result = svc.outputs.benefit_summary(intake_id)
    if isinstance(result, str):
        raise _output_error(result)
    return result


# --- helpers -------------------------------------------------------------------------------


def _found(view: TurnView | None) -> TurnView:
    if view is None:
        raise ApiError(404, "intake_not_found")
    return view


def _output_error(reason: str) -> ApiError:
    return (
        ApiError(404, "intake_not_found")
        if reason == "not_found"
        else ApiError(409, "not_submitted")
    )


def _turn(result: TurnResult) -> TurnView:
    """Map a service result to a response. A rejected turn that carries text for the user
    (e.g. "That message is too long") is a normal turn; one without is a client error."""
    if result.status == "not_found" or result.view is None:
        raise ApiError(404, "intake_not_found")
    if result.status == "stale":
        raise ApiError(409, "stale_turn", result.view)
    if result.status == "rejected" and not result.tells_user:
        raise ApiError(409, "action_not_available", result.view)
    return result.view
