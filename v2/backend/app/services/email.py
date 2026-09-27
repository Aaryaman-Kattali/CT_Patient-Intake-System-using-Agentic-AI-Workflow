"""The confirmation email: a plain service, never an agent tool (docs/V2_SPEC.md §11.3).

- `send_confirmation(intake_id, idempotency_key)` has NO recipient parameter. The recipient
  is read from this intake's stored, answered email field. There is no fallback to any
  other record: without a stored email, nothing is sent.
- Allowed only in SUBMITTED (the policy engine decides), which is reachable only after the
  user approved the review screen.
- The same idempotency key returns the first result and sends nothing again.
- No real email is ever sent. While SYNTHETIC_ONLY, only reserved example domains are allowed.
"""

import logging
import uuid
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path
from typing import Literal, Protocol
from uuid import UUID

from app.domain.fields import answer_value
from app.guardrails import policy
from app.services.persistence import IntakeRepository
from app.workflow.snapshot import EventRecord

log = logging.getLogger(__name__)

SUBJECT = "We have your form (demo)"
# Fixed text. It contains no answers from the form, not even a name.
BODY = (
    "Hello from the intake team.",
    "",
    "We have your form. Thank you for sending it.",
    "A staff member will read it and contact you.",
    "",
    "This is a demo. The details in it are made up.",
)
# Reserved names (RFC 2606 / 6761): mail to these can never reach a real person.
# The same set the repository's PII scan allows in test data.
RESERVED_DOMAINS = frozenset({"example.com", "example.org", "example.net"})
RESERVED_SUFFIXES = (".test", ".invalid")

EmailStatus = Literal["sent", "failed", "not_submitted", "no_email", "not_synthetic", "sending"]


@dataclass(frozen=True)
class Outgoing:
    to: str
    subject: str
    body: str


class EmailProvider(Protocol):
    name: str

    def send(self, message: Outgoing) -> None: ...


class ConsoleProvider:
    """Logs that an email would be sent. The recipient is never logged."""

    name = "console"

    def send(self, message: Outgoing) -> None:
        log.info("confirmation email logged by the console provider; nothing was sent")


class FileProvider:
    """Writes each email as an .eml file to an outbox folder outside the repository."""

    name = "file"

    def __init__(self, outbox: Path) -> None:
        self._outbox = outbox

    def send(self, message: Outgoing) -> None:
        mail = EmailMessage()
        mail["To"] = message.to
        mail["From"] = "intake-demo@example.org"
        mail["Subject"] = message.subject
        mail.set_content(message.body)
        self._outbox.mkdir(parents=True, exist_ok=True)
        (self._outbox / f"{uuid.uuid4().hex}.eml").write_bytes(bytes(mail))


@dataclass(frozen=True)
class EmailResult:
    status: EmailStatus
    repeated: bool = False  # this idempotency key was used before; nothing was sent now


def is_reserved_address(address: str) -> bool:
    domain = address.rpartition("@")[2].casefold()
    return domain in RESERVED_DOMAINS or domain.endswith(RESERVED_SUFFIXES)


_DENIALS: dict[str, EmailStatus] = {
    "side_effects_only_after_submit": "not_submitted",
    "no_stored_email": "no_email",
}


class EmailService:
    def __init__(self, repo: IntakeRepository, provider: EmailProvider) -> None:
        self._repo = repo
        self._provider = provider

    def send_confirmation(self, intake_id: UUID, idempotency_key: str) -> EmailResult:
        snap = self._repo.load(intake_id)
        if snap is None:
            raise LookupError("intake not found")
        decision = policy.decide(snap.state, snap.answers, policy.SideEffect("send_email"))
        recipient = answer_value(snap.answers, "email")
        if not decision.allowed or recipient is None:
            return self._deny(intake_id, _DENIALS.get(decision.reason, "not_submitted"))
        if not is_reserved_address(recipient):
            return self._deny(intake_id, "not_synthetic")
        first = self._repo.claim_email(intake_id, idempotency_key, self._provider.name)
        if first is not None:
            return EmailResult(status=_status(first.status), repeated=True)
        status = self._deliver(Outgoing(recipient, SUBJECT, "\n".join(BODY)))
        event = EventRecord(type="email_sent" if status == "sent" else "email_failed")
        self._repo.finish_email(intake_id, idempotency_key, status, (event,))
        return EmailResult(status=status)

    def _deliver(self, message: Outgoing) -> EmailStatus:
        try:
            self._provider.send(message)
        except Exception:  # the provider failed: report it, never crash the request
            log.exception("confirmation email failed", extra={"provider": self._provider.name})
            return "failed"
        return "sent"

    def _deny(self, intake_id: UUID, status: EmailStatus) -> EmailResult:
        self._repo.append_events(
            intake_id, (EventRecord(type="email_denied", payload={"reason": status}),)
        )
        return EmailResult(status=status)


_STORED: dict[str, EmailStatus] = {"sent": "sent", "failed": "failed", "sending": "sending"}


def _status(stored: str) -> EmailStatus:
    return _STORED.get(stored, "failed")


def build_provider(name: str, outbox: Path) -> EmailProvider:
    return FileProvider(outbox) if name == "file" else ConsoleProvider()
