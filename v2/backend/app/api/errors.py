"""Every error response is a fixed code plus a fixed plain-language message (audit B10).

Exception text, request bodies and field values never reach the response. Unexpected errors
are logged through the redacting logger and answered with `internal_error`.
"""

import logging
from types import MappingProxyType

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.schemas import ErrorBody, ErrorCode
from app.domain import templates as t
from app.workflow.view import TurnView

log = logging.getLogger(__name__)

MESSAGES: MappingProxyType[ErrorCode, str] = MappingProxyType(
    {
        "invalid_request": "The request was not in the right shape.",
        "intake_not_found": "We could not find this form.",
        "not_found": "This page does not exist.",
        "method_not_allowed": "That action is not allowed here.",
        "stale_turn": "This page was out of date. Here is the latest step.",
        "action_not_available": "That cannot be done at this step.",
        "form_incomplete": t.REVIEW_CANNOT_SUBMIT,
        "idempotency_key_required": "A request key is missing.",
        "email_not_submitted": "The email can be sent after the form is sent.",
        "email_no_address": "There is no email address in this form.",
        "email_not_synthetic": "This demo only sends mail to test addresses.",
        "email_failed": "The email could not be sent. Please try again later.",
        "not_submitted": "This is ready after the form is sent.",
        "resume_failed": "That code did not work. Please check it and try again.",
        "too_many_attempts": "Too many tries. Please wait a few minutes and try again.",
        "internal_error": "Something did not work on our side. Your saved answers are safe.",
    }
)

_HTTP_CODES: MappingProxyType[int, ErrorCode] = MappingProxyType(
    {404: "not_found", 405: "method_not_allowed", 422: "invalid_request"}
)


class ApiError(Exception):
    def __init__(self, status: int, code: ErrorCode, view: TurnView | None = None) -> None:
        super().__init__(code)
        self.status = status
        self.code = code
        self.view = view


def error_response(status: int, code: ErrorCode, view: TurnView | None = None) -> JSONResponse:
    body = ErrorBody(code=code, message=MESSAGES[code], view=view)
    return JSONResponse(status_code=status, content=body.model_dump(mode="json"))


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, error: ApiError) -> JSONResponse:
        return error_response(error.status, error.code, error.view)

    @app.exception_handler(RequestValidationError)
    async def _invalid(_: Request, __: RequestValidationError) -> JSONResponse:
        return error_response(422, "invalid_request")  # never echo the input back

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, error: StarletteHTTPException) -> JSONResponse:
        code = _HTTP_CODES.get(error.status_code, "invalid_request")
        status = error.status_code if error.status_code in _HTTP_CODES else 400
        return error_response(status, code)

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, error: Exception) -> JSONResponse:
        # The traceback goes to the log only, through the redacting filter.
        log.error("unhandled error", exc_info=error, extra={"error_class": type(error).__name__})
        return error_response(500, "internal_error")
