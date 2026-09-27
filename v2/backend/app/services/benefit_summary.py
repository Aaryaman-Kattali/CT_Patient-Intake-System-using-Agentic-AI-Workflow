"""The synthetic benefit summary demo (docs/V2_SPEC.md §11.2).

Deterministic. It reads only `full_name` from this intake's stored answers (passed in by the
caller). Every number is made up from a seed based on the intake id, and the output says so at
the top and at the bottom. It is not linked to any insurance plan or any other record.
"""

import random

from pydantic import BaseModel, ConfigDict

from app.domain.fields import answer_value
from app.workflow.snapshot import Snapshot

SYNTHETIC_LABEL = (
    "SYNTHETIC DEMO. These numbers are made up. They are not linked to any insurance plan."
)


class BenefitLine(BaseModel):
    model_config = ConfigDict(frozen=True)

    label: str
    value: str


class BenefitSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    label_top: str = SYNTHETIC_LABEL
    title: str = "Benefit summary (demo)"
    member_name: str
    source: str = "field:full_name"
    lines: tuple[BenefitLine, ...]
    label_bottom: str = SYNTHETIC_LABEL


def build_benefit_summary(snap: Snapshot) -> BenefitSummary:
    name = answer_value(snap.answers, "full_name")
    if name is None:
        raise LookupError("full_name is not answered")
    rng = random.Random(snap.id.int)  # noqa: S311 - made-up demo numbers, not security
    deductible = rng.choice((500, 1000, 1500, 2000))
    met = rng.randrange(0, deductible + 1, 50)
    lines = (
        BenefitLine(label="Plan", value="Demo Health Plan (not real)"),
        BenefitLine(label="Member ID", value=f"DEMO-{rng.randrange(10**7, 10**8)}"),
        BenefitLine(label="Coverage status", value="Active (demo)"),
        BenefitLine(label="Yearly deductible", value=f"${deductible:,}"),
        BenefitLine(label="Deductible met so far", value=f"${met:,}"),
        BenefitLine(label="Specialist visit copay", value=f"${rng.choice((20, 30, 40, 50))}"),
        BenefitLine(label="Out-of-pocket maximum", value=f"${rng.choice((4000, 6000, 8000)):,}"),
    )
    return BenefitSummary(member_name=name, lines=lines)
