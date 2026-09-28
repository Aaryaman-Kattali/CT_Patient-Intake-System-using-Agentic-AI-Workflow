"""Convert the owner's held-out conversations (datasets/heldout/*.md) to eval cases.

    uv run python -m evals.heldout      # writes datasets/heldout.jsonl

The owner's wording is kept exactly: each conversation line becomes one scripted turn,
unchanged. Only the Expected section is converted to canonical values (ISO dates, E.164
phone numbers, option ids), so it can be compared with what the form saved.
"""

import json
import re
from pathlib import Path

from app.domain.registry import FIELDS
from evals.cases import Case, Expected
from evals.common import say

FOLDER = Path(__file__).parent / "datasets" / "heldout"
OUTPUT = Path(__file__).parent / "datasets" / "heldout.jsonl"
FORMS = {
    "family inquiry for myself": "fi_self",
    "family inquiry for someone else": "fi_other",
    "provider referral": "pr",
}
STATUSES = {"skipped": "skipped", "answer later": "deferred", "not known": "not_known"}
BY_LABEL = {f.short_label.casefold(): f for f in FIELDS}


class HeldOutError(ValueError):
    pass


def _sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current = None
    for line in text.splitlines():
        if line.startswith("## "):
            current = line[3:].strip().casefold()
            sections[current] = []
        elif current is not None and line.strip():
            sections[current].append(line.rstrip())
    return sections


def _expected(field_label: str, raw: str) -> tuple[str, Expected]:
    fld = BY_LABEL.get(field_label.strip().casefold())
    if fld is None:
        raise HeldOutError(f"unknown field name: {field_label!r}")
    value = raw.strip()
    if value.casefold() in STATUSES:
        return fld.id, Expected(status=STATUSES[value.casefold()])
    if fld.options:
        option = next((o for o in fld.options if o.label.casefold() == value.casefold()), None)
        if option is None:
            raise HeldOutError(f"{fld.id}: no button {value!r}")
        return fld.id, Expected(status="accepted", value=option.id)
    if fld.input_type.value == "phone":
        digits = re.sub(r"\D", "", value)
        return fld.id, Expected(status="accepted", value="+1" + digits[-10:])
    if fld.input_type.value == "email":
        return fld.id, Expected(status="accepted", value=value.lower())
    return fld.id, Expected(status="accepted", value=value)


def convert(path: Path) -> Case:
    sections = _sections(path.read_text(encoding="utf-8"))
    form = next((line.strip("`- ").casefold() for line in sections.get("form", [])), "")
    if form not in FORMS:
        raise HeldOutError(f"{path.name}: form must be one of {sorted(FORMS)}")
    turns = tuple(line[2:] for line in sections.get("conversation", []) if line.startswith("- "))
    expected = dict(
        _expected(*line[2:].split(":", 1))
        for line in sections.get("expected", [])
        if line.startswith("- ") and ":" in line
    )
    if not turns:
        raise HeldOutError(f"{path.name}: no conversation lines")
    return Case(
        id=f"heldout-{path.stem}",
        category="heldout",
        persona="owner",
        intake=FORMS[form],
        book={},
        expected=expected,
        script=turns,
    )


def main() -> None:
    files = sorted(p for p in FOLDER.glob("*.md") if p.name != "TEMPLATE.md")
    cases = [convert(p) for p in files]
    with OUTPUT.open("w", encoding="utf-8", newline="\n") as f:
        for case in cases:
            f.write(json.dumps(case.model_dump(mode="json", exclude_defaults=True)) + "\n")
    say(f"{len(cases)} held-out cases -> {OUTPUT}")


if __name__ == "__main__":
    main()
