"""Staff summary and benefit demo: generated only in SUBMITTED, once, from this intake only.

The policy engine decides whether they may be generated. The builders receive this intake's
stored data from here; they cannot read anything else.
"""

from typing import Literal
from uuid import UUID

from app.domain.fields import Answers
from app.guardrails import policy
from app.services.benefit_summary import BenefitSummary, build_benefit_summary
from app.services.persistence import IntakeRepository
from app.services.staff_summary import StaffSummary, build_staff_summary
from app.workflow.snapshot import EventRecord
from app.workflow.states import State

Denied = Literal["not_found", "not_submitted"]


class StaffOutputs:
    def __init__(self, repo: IntakeRepository) -> None:
        self._repo = repo

    def staff_summary(self, intake_id: UUID) -> StaffSummary | Denied:
        stored = self._repo.staff_output(intake_id, "staff_summary")
        if stored is not None:
            return StaffSummary.model_validate(stored)
        snap = self._repo.load(intake_id)
        if snap is None:
            return "not_found"
        if not self._allowed(snap.state, snap.answers, "staff_summary"):
            return "not_submitted"
        summary = build_staff_summary(snap, self._repo.numbered_events(intake_id))
        content = self._repo.save_staff_output(
            intake_id,
            "staff_summary",
            summary.model_dump(mode="json"),
            (EventRecord(type="staff_summary_generated"),),
        )
        return StaffSummary.model_validate(content)

    def benefit_summary(self, intake_id: UUID) -> BenefitSummary | Denied:
        stored = self._repo.staff_output(intake_id, "benefit_demo")
        if stored is not None:
            return BenefitSummary.model_validate(stored)
        snap = self._repo.load(intake_id)
        if snap is None:
            return "not_found"
        if not self._allowed(snap.state, snap.answers, "benefit_demo"):
            return "not_submitted"
        content = self._repo.save_staff_output(
            intake_id,
            "benefit_demo",
            build_benefit_summary(snap).model_dump(mode="json"),
            (EventRecord(type="benefit_demo_generated"),),
        )
        return BenefitSummary.model_validate(content)

    @staticmethod
    def _allowed(
        state: State, answers: Answers, kind: Literal["staff_summary", "benefit_demo"]
    ) -> bool:
        return policy.decide(state, answers, policy.SideEffect(kind)).allowed
