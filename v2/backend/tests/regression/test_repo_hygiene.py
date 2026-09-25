"""Regression tests for audit items #1, #5, #10, B9, B11 and the Q3 decision."""

import os
import re
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import Settings, load_region_content
from app.main import create_app
from tests.conftest import API_KEY_VARS, BACKEND_DIR, REPO_ROOT

APP_DIR = BACKEND_DIR / "app"

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+\.)+[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?<!\d)(\(?\d{3}\)?[-. ]?\d{3}[-. ]\d{4})(?!\d)")
ALLOWED_EMAIL_DOMAINS = re.compile(
    r"@(example\.(com|org|net)|[\w.-]+\.(test|invalid)|users\.noreply\.github\.com|anthropic\.com)$"
)


def _is_fictional_phone(raw: str) -> bool:
    """Same rule as CLAUDE.md: NXX-555-0100 to NXX-555-0199 (e.g. 202-555-0100)."""
    digits = re.sub(r"\D", "", raw)
    return len(digits) == 10 and digits[3:6] == "555" and 100 <= int(digits[6:]) <= 199


def _run_git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-c", "safe.directory=*", *args],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def _git(*args: str) -> str:
    result = _run_git(*args)
    result.check_returncode()
    return result.stdout


def _repo_text_files() -> list[Path]:
    names = _git("ls-files", "--cached", "--others", "--exclude-standard").splitlines()
    paths = [REPO_ROOT / n for n in names]
    return [p for p in paths if p.is_file() and p.suffix not in {".pyc", ".png", ".jpg", ".ico"}]


# --- #1 model ids -----------------------------------------------------------


def test_no_hardcoded_model_ids() -> None:
    offenders = [
        str(p.relative_to(BACKEND_DIR))
        for p in APP_DIR.rglob("*.py")
        if p.name != "config.py" and "gemini-" in p.read_text(encoding="utf-8")
    ]
    assert offenders == []


# --- #5 no shared module state --------------------------------------------


def test_app_factory_creates_independent_state() -> None:
    first, second = create_app(), create_app()
    assert first is not second
    assert first.state.settings is not second.state.settings


# --- #10 personal data in repo --------------------------------------------


def test_tracked_files_contain_no_real_contact_data() -> None:
    findings: list[str] = []
    for path in _repo_text_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        rel = path.relative_to(REPO_ROOT).as_posix()
        findings += [
            f"{rel}: email {m.group(0)}"
            for m in EMAIL_RE.finditer(text)
            if not ALLOWED_EMAIL_DOMAINS.search(m.group(0))
        ]
        findings += [
            f"{rel}: phone {m.group(1)}"
            for m in PHONE_RE.finditer(text)
            if not _is_fictional_phone(m.group(1))
        ]
    assert findings == []


@pytest.mark.parametrize(
    "path",
    [
        ".env",
        "v2/backend/.env",
        "v2/backend/var/intake.db",
        "anything.sqlite3",
        "agentic-ai/collected_chatbot_data/x.json",
        "agentic-ai/agent/__pycache__/x.cpython-310.pyc",
    ],
)
def test_gitignore_covers_env_db_and_data(path: str) -> None:
    assert _git("check-ignore", "--no-index", path).strip() == path


def test_env_example_is_not_ignored() -> None:
    result = _run_git("check-ignore", "--no-index", "v2/backend/.env.example")
    assert result.returncode == 1  # 1 == not ignored


def test_synthetic_only_cannot_be_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYNTHETIC_ONLY", "false")
    with pytest.raises(ValidationError, match="SYNTHETIC_ONLY must be true"):
        Settings()


# --- B11 data inside source tree ------------------------------------------


def test_default_db_path_is_gitignored() -> None:
    db_path = Path(Settings().database_url.removeprefix("sqlite:///"))
    rel = db_path.relative_to(REPO_ROOT).as_posix()
    assert _git("check-ignore", "--no-index", rel).strip() == rel


# --- B9 no tests / CI -----------------------------------------------------


def test_ci_workflow_runs_tests_and_linters() -> None:
    ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    for step in (
        "uv sync --locked",
        "ruff check",
        "ruff format --check",
        "mypy",
        "pytest",
    ):
        assert step in ci, f"CI is missing: {step}"
    assert "-m live" not in ci


USES_RE = re.compile(r"^\s*(?:-\s*)?uses:\s*(?P<ref>\S+)", re.MULTILINE)
PINNED_RE = re.compile(r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$")


def test_workflow_actions_pinned_to_commit_sha() -> None:
    workflows = [
        *(REPO_ROOT / ".github" / "workflows").glob("*.yml"),
        *(REPO_ROOT / ".github" / "workflows").glob("*.yaml"),
    ]
    refs = [
        (wf.name, m.group("ref"))
        for wf in workflows
        for m in USES_RE.finditer(wf.read_text(encoding="utf-8"))
    ]
    assert refs, "no `uses:` lines found; the check would pass vacuously"
    unpinned = [
        f"{name}: {ref}"
        for name, ref in refs
        if not ref.startswith("./") and not PINNED_RE.match(ref)
    ]
    assert unpinned == []


# --- Q3 crisis text lives in region files, not code -------------------------


def test_crisis_text_loaded_from_region_file() -> None:
    lines = load_region_content("US").crisis.lines
    code = "\n".join(p.read_text(encoding="utf-8") for p in APP_DIR.rglob("*.py"))
    for line in lines:
        assert line not in code
    assert "988" not in code
    assert "911" not in code


# --- API key never needed by default suite ---------------------------------


def test_unit_tests_do_not_need_api_key() -> None:
    assert not [v for v in API_KEY_VARS if os.environ.get(v)]


@pytest.mark.parametrize(
    ("text", "flagged"),
    [
        ("call 312-867-" + "5309", True),
        ("call (312) 867-" + "5309", True),
        ("call 202-555-0100", False),
        ("call 202-555-0199", False),
        ("call 202-555-" + "0099", True),
        ("call 202-555-" + "0200", True),
        ("mail someone@" + "university.edu", True),
        ("mail alex@example.com", False),
        ("born 2004-05-04", False),
    ],
)
def test_contact_scanner_is_not_vacuous(text: str, flagged: bool) -> None:
    emails = [m for m in EMAIL_RE.finditer(text) if not ALLOWED_EMAIL_DOMAINS.search(m.group(0))]
    phones = [m for m in PHONE_RE.finditer(text) if not _is_fictional_phone(m.group(1))]
    assert bool(emails or phones) is flagged
