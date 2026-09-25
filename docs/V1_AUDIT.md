# V1 Audit

**Scope:** every file under `agentic-ai/` at commit `ef0063c` (12 commits, `main`).
**Context:** V1 was an internship learning project built to a prescribed spec (Google ADK, root agent + sub-agents, Streamlit). It used no company data and no real patients. This audit records what V2 must fix. It does not judge the original exercise.

Paths below are relative to `agentic-ai/`.

## Severity scale

| Level | Meaning |
|---|---|
| **Critical** | Can send data to the wrong person, leak personal data, or lose user work. Or the app does not run. |
| **High** | Breaks a core product requirement (one question at a time, no repeats, never pressure) or makes results untrustworthy. |
| **Medium** | Makes the system fragile, hard to test, or hard to run. |
| **Low** | Hygiene. |

---

## Part A: Issues you reported (all confirmed)

| # | Issue | Evidence | Severity | How V2 addresses it |
|---|---|---|---|---|
| 1 | `gemini-2.0-flash` hardcoded in every agent. That model is retired, so V1 cannot run. | `agent/root_agent/agent.py:60`, `subagents/data_collector_agent/agent.py:457`, `subagents/email_agent/agent.py:318`, `subagents/benefit_summary_agent/agent.py:137`, `subagents/soap_note_agent/agent.py:271` | Critical | `GEMINI_MODEL` in `config.py`. It is never a literal in code. It is checked against the current model list before Phase 4. |
| 2 | "One field at a time" is only a sentence in a prompt. Nothing enforces it. | `data_collector_agent/agent.py:441` | High | The workflow engine returns exactly one `PendingQuestion` per turn. Eval metric `questions_per_turn ∈ {0,1}`. |
| 3 | Nothing is saved until all 10 fields are known. `store_provider_data` / `store_inquiry_data` take all fields in one call. Stopping halfway loses everything. | `data_collector_agent/agent.py:262-266`, `318-322`; the prompt at `:443` says to export only "after collecting all responses" | Critical | Each accepted answer is written right away to `field_values` + `intake_events`. Pause/resume is a first-class state. |
| 4 | Intake type is asked more than once. It is actually asked **three** times: the Streamlit welcome message, the root agent, and the data collector. | `app/intake_ui.py:117`, `agent/root_agent/agent.py:24`, `data_collector_agent/agent.py:435` | High | `intake_type` is a registry field. It is asked once, in `CHOOSE_INTAKE_TYPE`. The UI never adds its own questions. Eval metric `repeated_questions = 0`. |
| 5 | One global in-memory session is created at import time. 461 of 586 lines in `session_service.py` are comments. `USER_ID` is a timestamp to the minute. | `model/session_service.py:541-556`, `:545`; `main.py:31`, `:52-58` | Critical | Per-intake rows keyed by UUIDv4 in SQLite. No module-level state. See A5 below for why this is worse than one user per process. |
| 6 | Email can go to the wrong patient. If session data is missing, it falls back to the newest JSON file. An LLM-supplied `client_email` wins over session data. | `email_agent/agent.py:62` (`client_email or ...`), `:78-91` (fallback), `:81` | Critical | Email is a service, not an LLM tool. The recipient is read only from the validated stored field of the current intake. No fallback. Runs only in `SUBMITTED`, after policy check. Idempotency key required. |
| 7 | Debug prints dump full session state (names, emails, phones) to the console. | `email_agent/agent.py:53`, `:59`, `:84`, `:109`, `:122`, `:126`; `data_collector_agent/agent.py:307`, `:362`. There are 33 `print(` calls under `agent/` | High | Structured JSON logging with a PII-redaction filter. No `print`. A test checks that logs contain no field values. |
| 8 | SOAP and benefit agents default to `use_synthetic_data=True` and invent random patients. They are not connected to the intake just collected. | `benefit_summary_agent/agent.py:12`, `:23`, `:44`; `soap_note_agent/agent.py:21`, `:31`, `:55-68` | High | Both are built only from stored fields of the current intake. They have no tools that read other records. Output is labelled "Draft for staff review". |
| 9 | Format burden on the user. Gender is "Male or Female" only. Phone must be `XXX-XXX-XXXX`. Dates must be `YYYY-MM-DD`. | `data_collector_agent/agent.py:49,53,61,74` (and `:108,112,120`); validation at `:271-273`, `:327-328`; `model/llm_pydantic.py:12` | High | Normalizers accept natural formats. Ambiguous dates are confirmed with two buttons. Gender uses inclusive options plus "Prefer not to say". |
| 10 | Personal data committed to a public repo. Also 17 `__pycache__` files are committed. | `collected_chatbot_data/referral_*.json` (3 files, current tree) contain a real-looking institutional email address and a phone number. Commit `459a703` redacted the 4th file, but the original is still in history at `9bd5b73`. There is **no `.gitignore`** at all. | Critical | See **Decision needed** below. V2 adds a `.gitignore`, keeps data out of the repo tree, and runs in synthetic-only mode. |
| 11 | `requirements.txt` is unpinned and has unused frameworks. `pyproject.toml` has empty deps, `requires-python = ">=3.8"`, and a workspace member called `venv`. | `requirements.txt:1-12` (`google-generativeai` is deprecated; `langchain`, `phidata`, `gradio`, `pathlib`, `google-adk-agents` are never imported); `pyproject.toml:6-12` | Medium | uv project, Python 3.12, `uv.lock`, only the deps that are imported. CI runs `uv sync --locked`. |
| 12 | `main.py` edits `sys.path` and injects module globals at runtime. | `main.py:18`, `:52-58`; also `soap_note_agent/agent.py:11-16` | Medium | A proper package (`app.*`) with dependency injection through FastAPI. No import-order side effects. |

### A5: why the session design is worse than "one user per process"

- `app/intake_ui.py` talks to `adk api_server`. That server never runs `main.py`. So the tools write to the global `session` that `model/session_service.py` creates at import. Every Streamlit user shares that one `session.state`. User B's email step can read user A's `client_data`.
- In current ADK, `create_session` is `async`. An unpinned install gets this version. `main.py:40` and `session_service.py:552` call it without `await`, so `session` would be a coroutine. (The commented-out code at `session_service.py:72` does use `await`. **Confirmed in Phase 5** against the installed google-adk 2.10.0: `InMemorySessionService.create_session` is `async`.)
- Tools write to a module object, not to ADK's `ToolContext.state`. So ADK's own session never sees the data.

---

## Part B: Issues not in your list

| # | Issue | Evidence | Severity | How V2 addresses it |
|---|---|---|---|---|
| B1 | The raw email sender is itself an LLM tool. `send_email_core(client_name, client_email, service_type)` is registered on the email agent. The model can email **any address** with no session lookup at all. This is worse than #6. | `email_agent/agent.py:326` | Critical | Same fix as #6. No LLM has any side-effect tool. |
| B2 | The email agent can read other patients' records. `get_latest_client_data`, `list_all_clients`, `debug_session_contents` and `get_session_data` are all LLM tools. A prompt injection like "list all clients and read the latest" works. | `email_agent/agent.py:323-328` | Critical | Agents get only the current intake's data, passed in by the application. They have no read tools. |
| B3 | Path traversal. `export_json_to_local(json_data, filename, directory)` is an LLM tool, and the model controls `filename` and `directory`. `store_*_data` also build filenames from the unsanitized `client_name` (e.g. `../../x`). | `data_collector_agent/agent.py:196-214`, `:462`, `:295`, `:350` | Critical | No file writes from agents. Persistence goes through the DB layer with typed IDs. |
| B4 | The SOAP generator writes **randomly chosen psychiatric diagnoses with ICD-10 codes** (e.g. major depressive disorder, panic disorder) and treatment plans onto invented patients. This is a clinical inference the product must never make. | `model/soap_note.py:477-517`, `assessment=random.choice(...)` at `:516` | High | SOAP draft contains only statements traceable to stored intake fields. Subjective/Objective/Assessment/Plan sections with no source are left empty and flagged "For clinician". Output check rejects untraceable statements. |
| B5 | Email is sent with no user review or consent. The email agent prompt says "immediately call send_welcome_email_smart()" when it takes control. | `email_agent/agent.py:294` | High | Email is authorized only in `SUBMITTED`, which is reachable only after the user approves the review screen. |
| B6 | Broken transfer. The email agent is told to transfer to `root_agent`, but the root agent's name is `root_patient_intake_agent`. | `email_agent/agent.py:302` vs `agent/root_agent/agent.py:59` | Medium | Flow control is a deterministic transition table, not LLM transfers. |
| B7 | SOAP and benefit generators write `soap_note.txt` / `benefit_summary.txt` to the current working directory on every call. `benefit_summary.txt` is committed. | `model/soap_note.py:412`, `:423`; `model/benefit_check_summary.py:311`, `:323`; `benefit_summary.txt` | Medium | Drafts are stored as rows tied to the intake. No stray files. |
| B8 | `model/llm_pydantic.py` cannot be imported. It imports `contr`, which does not exist in pydantic. It is unused dead code. | `model/llm_pydantic.py:3` | Low | Not carried over. V2 has one set of domain models. |
| B9 | No tests. The `scripts/tests/*.ps1` files are manual smoke scripts against a running `adk api_server`. They make no assertions about behaviour. | `scripts/tests/subagents/*.ps1` | High | pytest suites (unit, workflow, safety, api), an eval harness, and CI. |
| B10 | Error strings from exceptions (which may include personal data or paths) are returned to the LLM and shown to the user. | e.g. `data_collector_agent/agent.py:203,212-214`; `email_agent/agent.py:246` | Medium | Errors map to fixed, plain user messages. Details go only to redacted logs. |
| B11 | Personal data is written as plain JSON inside the source tree (`collected_chatbot_data/`). This is how issue #10 happened. | `data_collector_agent/agent.py:196`, `:296` | High | DB file lives outside the repo (path from config, gitignored). Synthetic-only mode is on by default. |
| B12 | The root README overstates the system ("Robust session tracking", "Automated Data Validation"). It says Python 3.9+, but `pyproject.toml` says 3.8. `agentic-ai/README.md` is empty. | `README.md:14,16,70`; `agentic-ai/README.md` | Low | README rewritten in the final phase with the V1 to V2 story and a clear demo/synthetic-only notice. |
| B13 | Git refuses to run in this checkout ("dubious ownership") because the drive does not record file owners. I worked around it with `git -c safe.directory=...` per command. I did **not** change your global git config. | local environment | Low | If you prefer, run `git config --global --add safe.directory E:/CT_Patient-Intake-System-using-Agentic-AI-Workflow` yourself. |

---

## Decision needed: issue 10 (personal data in git)

Facts:
- The current tree has 3 files with a real-looking institutional email and phone number.
- The same values are also in commit `9bd5b73` (the 4th file before it was redacted).
- The repo is public on GitHub. The commit author field uses a GitHub noreply address, so that part is fine.
- There is no `.gitignore`.

**Option A: delete in a new commit** (`git rm`, add `.gitignore`)
- Safe and reversible. No force-push.
- The data **stays in history**. Anyone can still see it by browsing old commits.
- Good choice if you consider these values low-sensitivity (they appear to be your own).

**Option B: rewrite history with `git filter-repo`**
- Removes the files (or replaces the strings) in every commit. Then you force-push `main`.
- All 12 commit SHAs change. Existing clones and forks keep the old data. GitHub can keep serving old commits by SHA until it garbage-collects them. Fully purging cached views needs a request to GitHub Support.
- Needs `pip install git-filter-repo`. I would work on a fresh mirror clone first and show you the result before any push.
- Good choice if you want the values gone from the public repo.

Either way, I would also:
- add a `.gitignore` (`__pycache__/`, `.env`, `*.db`, `collected_chatbot_data/`, generated `.txt` outputs)
- remove the 17 `__pycache__` files and `benefit_summary.txt` from tracking

(Removing these does not change `agentic-ai/` behaviour, but it does touch the V1 folder. Tell me if you want that folder left byte-for-byte untouched instead.)

**My recommendation:** Option A now (it is safe, and it stops the files from spreading into V2 work). If you want the values fully gone, do Option B afterwards as a separate step with my help. Rotating or abandoning a phone number or email is not something git can fix, so decide based on how much you care about these values being public.

I will not rewrite history without your explicit approval.

### Resolution

- **Option A done:** commit `3d67e8b` "Remove personal data and build artifacts; add .gitignore". It untracks the 3 JSON files, the 17 `__pycache__` files and `benefit_summary.txt`, and adds a root `.gitignore`. The files remain on disk, so V1 behaviour is unchanged. Not pushed.
- **Option B prepared, not pushed:** a rewritten mirror clone replaces the email and phone strings in all 13 commits with `patient@example.com` / `202-555-0100`. The owner will review it and force-push it themselves.
