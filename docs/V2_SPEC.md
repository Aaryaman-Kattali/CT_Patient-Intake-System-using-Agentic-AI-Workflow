# V2 Specification: Patient Intake Assistant

Status: **draft for approval**. Nothing here is built yet.
Related: [V1_AUDIT.md](V1_AUDIT.md) (audit item IDs like `#6` or `B4` are used throughout).

---

## 1. Product

### 1.1 What it is

An intake assistant for a hospital or clinic. It helps autistic patients, and people filling in forms for them, give the information a normal intake form asks for. It asks **one question at a time**, in plain literal language. It fills the patient's information page in the background as answers arrive.

Standard multi-field forms overwhelm many people in this group. The single most important requirement is one question per turn, in wording that does not change. This overrides generic UX advice such as "show the whole form so people can scan it".

### 1.2 Who uses it

| Role | Description |
|---|---|
| Patient | Fills in the form about themselves. |
| Family member or carer | Fills in the form for the patient (Family Inquiry). |
| Referring health worker | Sends a Provider Referral for a patient. |
| Staff (read-only, demo) | Reads the submitted intake and the staff summary. |

### 1.3 Demo and synthetic-data only

This is a portfolio demo. It must never process real personal or health data.
- `SYNTHETIC_ONLY` is a config setting that defaults to `true`. The app **refuses to start** if it is `false` in this version (there is no supported real-data mode).
- In synthetic mode, the SMTP email provider only sends to reserved test domains (`example.com`, `example.org`, `example.net`, `*.test`, `*.invalid`). Any other recipient is refused. The default provider is `console`, which sends nothing.
- The UI shows a permanent banner: "Demo only. Do not enter real personal information."
- The README states this clearly.
- There is no auth beyond a demo session token (see §9).

### 1.4 Product decisions recorded

| ID | Decision | Reason |
|---|---|---|
| D1 | **SOAP note generation is removed from V2.** It is replaced by an **Intake summary for staff** (§11.1). This is a structured handover built only from stored fields of the current intake. Every statement cites its source `field_id` (or event id). It contains no diagnoses, no assessments and no plans. | Audit **B4**: V1's SOAP generator attached randomly chosen psychiatric diagnoses with ICD-10 codes and treatment plans to invented patients. A SOAP note's Assessment and Plan sections are clinical by definition. This product is administrative and must never diagnose or infer medical facts. |
| D2 | **Benefit summary is kept only as a clearly labelled synthetic demo** (§11.2). | It shows the V1 feature working end to end. It cannot be real, because there is no insurance integration. Every output carries a "SYNTHETIC DEMO" label. |
| D3 | V1's `contact_details` field is dropped. `preferred_contact_method` now chooses which existing contact field is required. | `contact_details` asks again for a phone or email the user already gave. V1's own saved record contains the answer "already given". That is a repeated question. |
| D4 | Only one component uses an LLM: the **understanding agent**. Question choice, completion, email, staff summary and benefit demo are all deterministic code. | Design principle P2. See §6 for the one optional LLM experiment. |
| D5 | In **Family Inquiry**, `phone`, `email` and `address` belong to the **respondent** (the person filling in the form), not the patient. Their questions always use "you" wording. A new field `respondent_name` (FI only, required when relationship ≠ "me") is asked right after `relationship`. In **Provider Referral**, the contact fields stay the patient's. | A child patient usually has no phone, and the clinic needs the parent's or carer's details. V1's `contact_details` field most likely covered this respondent contact. **D3's reasoning only held for relationship = "me".** `contact_details` stays dropped, because D5 now covers its purpose without asking twice. (Owner review of §5.3.) |

---

## 2. Design principles (non-negotiable)

These are copied into `CLAUDE.md`.

- **P1. One question per turn.** Every assistant message asks at most one thing. This is enforced in code: the workflow engine returns exactly zero or one `PendingQuestion`. It is not a prompt instruction.
- **P2. The system decides, the LLM interprets.** A deterministic workflow engine picks the next question from the field registry. The LLM never decides question order, when the intake is complete, or whether to send an email.
- **P3. Predictable, fixed wording.** Question text comes from the field registry as fixed, reviewed plain-language templates. The same question reads the same way every time. The LLM never rephrases questions. It is used to understand replies. "Why are you asking this?" is answered from a fixed explanation stored per field.
- **P4. Save after every answer.** Each accepted answer is saved straight away as an event. The user can leave at any time and resume exactly where they were.
- **P5. Tolerate more, ask less.** If a reply contains extra information (for example name and date of birth together), extract it but do not silently accept it. Confirm each extra value with a simple yes/no question on the following turns, one at a time. Then skip the questions it already answered.
- **P6. Never pressure.** No timers, no "please hurry", no guilt. "I don't know" and "skip" are always valid answers for non-required fields. Required fields can be deferred. The review screen shows what is still missing.
- **P7. Agents propose, the application decides.** All LLM output is structured (Pydantic via Gemini structured output). It is validated and passed through a policy check before it changes state or triggers a side effect.
- **P8. Side effects are services, not agents.** Email is a plain service. The workflow calls it after the user approves the review step. The recipient always comes from validated stored state, never from LLM arguments. There is no fallback to other records.
- **P9. Administrative, not clinical.** The system collects information. It never diagnoses, suggests conditions or infers medical facts. Staff-facing outputs are clearly labelled and built only from stored data.

Agent rules (also in `CLAUDE.md`):
- **No agent has side-effect tools.**
- **No agent has tools that read records other than the current intake.** That data is passed in by the application, not fetched by the agent.
- **No agent writes files.**

---

## 3. Accessibility requirements

These define "good" for this product.

### 3.1 Language

- Plain, literal language. No idioms, metaphors, sarcasm, or indirect requests. "Could you tell me..." becomes "What is your date of birth?".
- Short sentences. Every question template: reading grade ≤ 6 (Flesch-Kincaid, via `textstat`), ≤ 15 words, exactly one `?`. A unit test checks every template (§13).
- No exclamation marks, no emoji, no "Great!" or "Perfect!". A short neutral acknowledgement is allowed ("Saved.").
- Never imply the user made a mistake. Validation retries use fixed templates such as "I could not read that as a date. Here is an example: May 4, 2004." They never say "invalid", "wrong" or "error".

### 3.2 Each question screen

- One question, shown as a heading.
- For fixed-option fields: buttons. Always include "I'm not sure". Where appropriate, include "Prefer not to say".
- For free-text fields: an example answer under the input ("Example: May 4, 2004").
- An always-visible **"Why are you asking this?"** link in the same place on every screen. It shows the field's fixed `why` text.
- An always-visible **"Take a break"** button. It saves, then shows how to come back.
- A **"Skip"** button on non-required fields, and "Answer later" on required fields.
- Progress: "Question 4 of about 12", plus section names with checkmarks.

### 3.3 Start screen

States roughly how many questions there are ("about 12"), that the user can stop at any time, and that answers are saved as they go. It has one button: "Start".

### 3.4 Formats are the system's job

- Dates: "May 4th 2004", "4 May 2004", "2004-05-04", "05/04/2004" and similar are all accepted. When a date could mean two things (both numbers ≤ 12 and different, e.g. `04/05/2004`), the system asks with **two buttons**: "April 5, 2004" / "May 4, 2004". Dates are always shown back with the month as a word.
- Phone: any common format is accepted and normalized to E.164 (`phonenumbers`, default region from config).
- Email: validated with `email-validator` (no deliverability check). The domain is lower-cased.
- Gender: Woman, Man, Non-binary, Another gender (with a text box on the same screen), Prefer not to say, I'm not sure.

### 3.5 Corrections and conflicts

- **Conflict** (a new value for an already-saved field, without the user saying it is a correction): "Earlier you said May 4, 2004. Now you said June 4, 2004. Which one is correct?" Both values are shown as buttons, plus "Neither".
- **Explicit correction** ("sorry, my birthday is May 14"): saved directly **only if** the reply kind is CORRECTION **and** the new value is `explicit` and quoted from the user's message (`raw_text` check, §6.3). The next message starts with the full new value, "Updated: date of birth is May 14, 2004.", and shows an **Undo** button next to it, followed by the next question. Undo restores the previous value and status (`correction_undone` event). It is offered only on the turn right after the correction. Inferred or unclear changes always go through the conflict question.
- The wording never suggests fault.

### 3.6 WCAG 2.2 AA (web)

Particular attention to:
- 2.2.1 Timing Adjustable: there are no time limits.
- 2.3.3 / `prefers-reduced-motion`: no animation when reduced motion is set, and only minimal animation otherwise.
- 2.4.7 / 2.4.11 Focus visible and not obscured.
- 2.5.8 Target size: buttons at least 44×44 px (above the 24 px minimum).
- 3.2.6 Consistent Help: the "Why" link and "Take a break" button stay in the same place on every screen.
- **3.3.7 Redundant Entry**: this is the same idea as "never ask twice".
- 3.3.8 Accessible Authentication: the resume code can be copied and pasted. There are no puzzles.
- Full keyboard use. Focus moves to the new question heading on each turn. Acknowledgements are announced through `aria-live="polite"`.
- Adjustable text size (100 / 125 / 150 / 200 %), remembered per browser.
- Calm visual design: neutral palette, no red for "errors" (a neutral note with an icon and text instead), generous spacing, one column.

---

## 4. Architecture

### 4.1 Overview

```
 Browser (React SPA)
   │  REST (JSON)
   ▼
 FastAPI  ── api/ ──────────────────────────────────────────────┐
   │                                                            │
   ▼                                                            │
 workflow/engine  ◄── domain/registry (fields, templates,       │
   │    ▲               normalizers, validators)                │
   │    │ ReplyUnderstanding (proposals only)                   │
   │    │                                                       │
   │  agents/understanding (ADK LlmAgent, no tools,             │
   │    │                   output_schema = ReplyUnderstanding) │
   │    └─ guardrails/input  → guardrails/output                │
   │                                                            │
   ├─► guardrails/policy.decide(state, action) → allow/deny/confirm
   │                                                            │
   ├─► services/persistence (SQLite: intakes, field_values,     │
   │                         intake_events, llm_calls, ...)     │
   └─► services/{email, staff_summary, benefit_demo}  ◄─────────┘
         (only in SUBMITTED, only via policy)
```

A single turn goes like this:
1. The API receives a reply for intake `X` and loads its snapshot from the DB.
2. **Button replies** (option id, yes/no, conflict choice) go straight to the engine. There is **no LLM call**.
3. **Free-text replies** go to the input guardrails, then the understanding agent, then the output guardrails. The result is a list of validated proposals.
4. The engine turns the reply into candidate actions. Each action passes `policy.decide`. Allowed actions are applied in one DB transaction, and events are appended.
5. The engine picks the next single question. The API returns a `Turn` (§9.2).

### 4.2 Stack

| Area | Choice |
|---|---|
| Runtime | Python 3.12 |
| Packaging | `uv` with committed `uv.lock` |
| Web | FastAPI, Uvicorn |
| Models | Pydantic v2, `pydantic-settings` |
| DB | SQLite via SQLModel (SQLAlchemy 2). Types chosen to port to Postgres unchanged (UUID as `Uuid`, JSON as `JSON`, timezone-aware `DateTime`). `create_all` for the demo. Alembic is added only if we move to Postgres. |
| LLM | Google ADK (`google-adk`, current 2.x, pinned) + `google-genai` (current, pinned). **Not** the deprecated `google-generativeai`. |
| Model | `GEMINI_MODEL` in config, never a literal in code. Proposed default: `gemini-3.5-flash-lite` (listed as current and stable on 2026-09-26; `gemini-2.0-flash` is listed as shut down). This will be re-checked against the docs before Phase 4. |
| Parsing | Own small date parser (fully deterministic: it never fills in a missing year or day, which `python-dateutil` does silently), `phonenumbers`, `email-validator` |
| Quality | ruff (with `T201` "no print"), mypy (strict on `app/`), pytest, hypothesis, pre-commit |
| Frontend | React + TypeScript + Vite. No SSR is needed: this is a single-page, one-question flow behind a JSON API, so Next.js adds nothing. Vitest + Testing Library, `axe-core`, Playwright for the keyboard walkthrough. |
| Transport | Plain REST. SSE only if a concrete need appears. |
| Observability | stdlib `logging` with a small JSON formatter and a PII-redaction filter, plus the `llm_calls` table. OpenTelemetry is optional, last. |

**ADK note:** before writing agent code (Phase 4), I will read the installed ADK version's API. Specifically I will check how `LlmAgent(output_schema=...)` passes the schema to Gemini, the `Runner`/session API, and whether `create_session` is async. If ADK does not give reliable schema-constrained output, the understanding agent will call `google-genai` directly with `response_schema`, and ADK will stay only as the agent wrapper. I will report this, not decide it silently.

### 4.3 Repository layout

```
agentic-ai/                 # V1 reference, untouched
docs/                       # V1_AUDIT.md, V2_SPEC.md, EVAL_RESULTS.md
CLAUDE.md
v2/
  backend/
    pyproject.toml, uv.lock
    app/
      main.py               # app factory; no module-level mutable state
      config.py             # Settings (pydantic-settings)
      api/                  # routes, request/response schemas, token dependency
      domain/               # registry.py, fields.py, models.py,
                            # normalizers.py, validators.py, templates.py
      workflow/             # states.py, transitions.py, engine.py, selection.py
      agents/               # understanding.py (ADK), prompts.py
      guardrails/           # input.py, output.py, policy.py, redaction.py, distress.py
      services/             # persistence.py, email.py, staff_summary.py,
                            # benefit_demo.py, audit.py
    tests/
      unit/  workflow/  safety/  api/  regression/
  frontend/
  evals/
    datasets/               # *.jsonl synthetic conversations
    personas/
    metrics/
    runner.py
    v1_adapter.py           # drives V1 on the baseline branch
```

The docs stay at the repo root `docs/` (the audit already lives there) rather than `v2/docs/`.

---

## 5. Field registry

### 5.1 Field definition

```python
class InputType(str, Enum):
    TEXT = "text"; DATE = "date"; CHOICE = "choice"; PHONE = "phone"; EMAIL = "email"

class Option(BaseModel):
    id: str                   # stable id stored in DB, e.g. "parent"
    label: str                # button text, e.g. "My child"
    special: Literal["not_sure", "prefer_not"] | None = None
    free_text: bool = False   # shows a text box on the same screen ("Something else (type it)")

class Condition(BaseModel):   # all must hold
    field_id: str
    equals: str | None = None
    in_: list[str] | None = None

class FieldDef(BaseModel):
    id: str
    section: str
    order: int
    required: Literal["must_have", "required", "optional", "conditional"]
    # must_have:   blocks submit until answered
    # required:    asked like must_have, but can end as "not known" on review
    # optional:    skip / "I'm not sure" is final
    # conditional: tier decided by the contact rule (§5.3 note ¹)
    question_self: str        # "What is your date of birth?"
    question_other: str       # "What is the patient's date of birth?"
    label_self: str           # "your date of birth"   (used in confirm/conflict templates)
    label_other: str          # "the patient's date of birth"
    short_label: str          # "date of birth" (review screen, "Updated: ...", staff summary)
    why: str                  # fixed "Why are you asking this?" text
    help: str                 # fixed "What does this mean?" text
    example: str | None       # "May 4, 2004"
    input_type: InputType
    options: list[Option] = []
    normalizer: str           # key into normalizers registry
    validator: str            # key into validators registry
    conditions: list[Condition] = []
    about_respondent_in: frozenset[IntakeType] = frozenset()  # D5: FI contact fields
    not_sure: Literal["clarify", "answer", "defer"]
    # Applies only while the field is effectively must_have/required.
    # On an effectively optional field, "I'm not sure" / "I don't know" is always FINAL:
    # status dont_know, never asked again, never listed on review.
    # clarify: show `help` + same buttons again (intake_type only)
    # answer:  "I'm not sure" is a complete answer staff can follow up on
    # defer:   status deferred; shown on review as "Still needed"
```

Wording rule (deterministic, one function):
- A field is **about the respondent** if the intake type is in `about_respondent_in`. Otherwise it is about the patient.
- Use `question_self` if the field is about the respondent, **or** the respondent is the patient (FI with relationship "Me").
- Use `question_other` otherwise.

Both templates are fixed and reviewed. The registry is loaded from Python (typed), not YAML, so mypy checks it.

### 5.2 Next-question selection (deterministic)

```
applicable = [f for f in registry if conditions_met(f, values)]
pending_queue non-empty         → that item (extra confirmation or conflict)
first must_have/required field (effective tier) with no saved status  (by order)
first optional field (effective tier) with no saved status
otherwise                       → REVIEW
```

A field with **any** saved status (answered, skipped, deferred, dont_know, unknown_confirmed) is **never asked again automatically**, even if its tier changes later (e.g. an optional email marked dont_know becomes must_have when the preferred method changes to Email). Such a field appears on the review screen instead. It appears on the review screen as "Still needed". So the system never repeats a question on its own.

Review screen and submit (Q1, updated):

| Effective tier | Missing field shown on review as | Actions | Blocks submit? |
|---|---|---|---|
| must_have | Still needed | Answer now | **yes** |
| required | Still needed | Answer now · I don't know this | no |
| required, marked "I don't know this" | Not known | Answer now | no |
| optional (skipped / dont_know / never answered) | not listed | – | no |

"I don't know this" saves status `unknown_confirmed` and appends a `field_marked_unknown` event. Submit is allowed once every effectively must_have field is answered. A required field still deferred at submit appears in the staff summary as "Not answered, please follow up". One marked `unknown_confirmed` appears as "Not known, please follow up".

### 5.3 Field list (owner-reviewed wording)

Intake types: `family_inquiry` (FI), `provider_referral` (PR). "Self / other" wording follows the rule in §5.1. Fields marked **R** in "About" are about the respondent in FI.

| # | id | Applies to | About | Required | Type | Question (self / other) | Example / options | `not_sure` |
|---|---|---|---|---|---|---|---|---|
| 1 | `intake_type` | all | – | must_have (not deferrable) | choice | "Which one describes you?" | I want care for myself or someone I look after · I work in health care and I am sending a referral · I'm not sure | clarify² |
| 2 | `relationship` | FI | – | must_have | choice | "Who is this form for?" | Me · My child · My parent · My partner · My brother or sister · Someone I look after · Another family member · I'm not sure | answer |
| 3 | `respondent_name` | FI, relationship ≠ `me` | R | must_have | text | "What is your name?" | Jordan Rivera | defer |
| 4 | `full_name` | all | patient | must_have | text | "What is your full name?" / "What is the patient's full name?" | Alex Rivera | defer |
| 5 | `date_of_birth` | all | patient | required | date | "What is your date of birth?" / "What is the patient's date of birth?" | May 4, 2004 | defer |
| 6 | `preferred_contact_method` | FI | R | required⁴ | choice | "How do you want us to contact you?" | Phone call · Text message · Email · Letter in the mail · I'm not sure | answer |
| 7 | `phone` | all | R in FI, patient in PR | conditional¹ | phone | "What is your phone number?" / "What is the patient's phone number?" | 202-555-0100 | defer |
| 8 | `email` | all | R in FI, patient in PR | conditional¹ | email | "What is your email address?" / "What is the patient's email address?" | alex@example.com | defer |
| 9 | `address` | all | R in FI, patient in PR | conditional¹ | text | "What is your home address?" / "What is the patient's home address?" | 12 Oak Street, Springfield, IL 62701 | defer |
| 10 | `inquiry_reason` | FI | patient | required | choice + text³ | "What do you want help with?" / "What does the patient need help with?" | An autism assessment · Therapy or support · Help at school or work · Something else (type it) · I'm not sure | answer |
| 11 | `referral_provider_name` | PR | – | required | text | "What is the name of the provider who made this referral?" | Dr. Sam Lee | defer |
| 12 | `referral_type` | PR | – | required | choice | "What type of referral is this?" | Physician · Specialist · Emergency · I'm not sure | answer |
| 13 | `referral_date` | PR | – | required | date | "What date was the referral made?" | September 1, 2026 | defer |
| 14 | `referral_mode` | PR | – | optional | choice | "How was the referral sent?" | Fax · Phone · Web form · I'm not sure | final |
| 15 | `preferred_name` | all | patient | optional | text | "What name do you want us to use for you?" / "What name does the patient want us to use?" | Alex | final |
| 16 | `gender` | all | patient | optional | choice + text | "What is your gender?" / "What is the patient's gender?" | Woman · Man · Non-binary · Another gender (type it) · Prefer not to say · I'm not sure | final |

In PR the respondent is a health worker, so "self" wording is never used for patient fields. `referral_provider_name`, `referral_type`, `referral_date` and `referral_mode` have a single wording.

¹ **Contact rule** (checked before submit):
- **FI:** `phone`, `email` and `address` are the **respondent's**, and their questions always use "you" wording, whoever the patient is (D5). The field matching `preferred_contact_method` is **must_have** (Phone call or Text message → `phone`, Email → `email`, Letter in the mail → `address`). The other two are optional. If `preferred_contact_method` is "I'm not sure", deferred or not known, the **phone-or-email group** applies.
- **PR:** `phone`, `email` and `address` are the **patient's**. The **phone-or-email group** applies. `address` is optional.
- **Phone-or-email group:** the group is must_have until one member has a value. `phone` is asked first as must_have. If `phone` is deferred, `email` becomes must_have and is asked next. Once either has a value, the other becomes optional. Both are listed on review until one is answered.

² **`intake_type` "I'm not sure"** is a **clarification**, not an answer. Tapping it shows one fixed line explaining each option ("Choose the first one if you want care for yourself or someone you look after. Choose the second one if you are a health worker sending a patient to us."). Then it shows the same two buttons again. Nothing is saved, and a `clarification_shown` event is recorded. It does **not** count toward `repeated_questions` (§6.4, §14.2).

³ **`inquiry_reason`** is a choice with a text box for "Something else (type it)". The stored value is the option id, plus the typed text verbatim for `something_else`. `help` text: "A few words is enough." **P9 check:** the options name the *service being requested*, chosen by the user. They are administrative routing categories, not conditions. The system never infers a condition from them. The staff summary shows them as "Asked for: …", and free text is quoted as the user's own words.

`not_sure` column:
- *answer*: "I'm not sure" is saved as a complete answer that staff can follow up on.
- *defer*: status `deferred`, shown on review (§5.2).
- *final*: the field is optional, so "I'm not sure" is a final answer: status `dont_know`, never asked again, never listed on review.
- Contact fields follow *defer* while they are must_have on the current path and *final* while they are optional.

⁴ `preferred_contact_method` is **required** (not must_have): if the respondent does not know, the phone-or-email group still guarantees a way to contact them. `relationship = not_sure` uses "other" wording and asks `respondent_name`.

Once `preferred_name` is given, it is used in greetings only: the resume screen ("Welcome back, Alex.") and the review screen heading. It is never inserted into question templates, so question wording stays fixed (P3).

Approximate totals:

| Path | Required | Optional | Total |
|---|---|---|---|
| FI, relationship = me | 7 (intake_type, relationship, full_name, date_of_birth, preferred_contact_method, 1 contact field, inquiry_reason) | 4 (2 other contact fields, preferred_name, gender) | 11 |
| FI, relationship ≠ me | 8 (as above + respondent_name) | 4 | 12 |
| PR | 7 (intake_type, full_name, date_of_birth, phone or email, referral_provider_name, referral_type, referral_date) | 5 (other of phone/email, address, referral_mode, preferred_name, gender) | 12 |

The start screen is shown before the intake type is known, so it says "about 12 questions". After that, progress uses the exact count for the path.

Mapping to V1 values is kept for comparison. For example `relationship=child` means the respondent is the patient's parent, which is V1's `Parent`.

---

## 6. Reply understanding (the LLM's only job)

### 6.1 Output model

```python
class ReplyKind(str, Enum):
    ANSWER = "answer"
    ANSWER_PLUS_EXTRA = "answer_plus_extra"
    CORRECTION = "correction"
    CLARIFICATION = "clarification"
    DONT_KNOW = "dont_know"
    SKIP = "skip"
    PAUSE = "pause"
    OFF_TOPIC = "off_topic"
    DISTRESS = "distress"
    UNSAFE = "unsafe"

class FieldProposal(BaseModel):
    field_id: str
    raw_text: str                         # exact span from the user's message
    value: str                            # LLM's reading; see 6.3
    source: Literal["explicit", "inferred"]

class ReplyUnderstanding(BaseModel):
    kind: ReplyKind
    proposals: list[FieldProposal] = []
    clarification: Literal["why", "meaning"] | None = None   # only for CLARIFICATION
    distress_level: Literal["overwhelmed", "crisis"] | None = None  # only for DISTRESS
```

I added two small fields to your sketch. `clarification` separates "why are you asking?" (show the `why` text) from "what do you mean?" (show the `help` text). `distress_level` separates overwhelm from crisis. Both select fixed text. Neither lets the LLM write text for the user. There are no confidence scores.

### 6.2 What the agent sees

- The pending question: field id, input type, option ids and labels.
- A compact list of applicable field ids with a one-line description and type (so it can tag extras).
- The set of field ids that already have a value. **Not the values themselves.** The engine detects conflicts by comparing normalized values, so the LLM does not need stored data.
- The user's message, wrapped in clear delimiters and marked as data.

It has **no tools**. It is stateless per call: a fresh ADK session each time, with no conversation memory. The application passes in everything it needs.

### 6.3 Turning proposals into actions (deterministic)

For each proposal:
1. **Reject** if `field_id` is not in the registry or not applicable.
2. **Reject** if `raw_text` does not appear in the user's message (compared case-insensitively, with whitespace collapsed).
3. The **value is derived from `raw_text` by our normalizer**, not taken from the LLM's `value`. For text fields, the stored value is the `raw_text` span, trimmed. For choice fields with inferred mapping ("my mum" → `parent`), the LLM's `value` must be a valid option id, and `source` is forced to `inferred`. If the LLM's `value` disagrees with the normalized `raw_text`, the proposal is rejected (hallucination check).
4. **Validate.** On failure, show the field's fixed retry template.
5. **Decide acceptance:**

| Proposal | Result |
|---|---|
| explicit, pending field, valid | accept, save |
| explicit, other field, valid, field empty | queue a yes/no confirmation (P5) |
| inferred (any field) | queue a yes/no confirmation |
| any, field already has a different value, kind ≠ CORRECTION | queue a conflict question |
| explicit, kind = CORRECTION, `raw_text` quoted from message, valid | save the new value, record a `field_corrected` event, show "Updated: <label> is <full value>." + Undo |
| inferred, or kind ≠ CORRECTION, field already has a value | conflict question (never a silent overwrite) |
| ambiguous date | queue a two-button date choice |

### 6.4 How the engine handles each kind

| Kind | Engine behaviour | Message to the user |
|---|---|---|
| ANSWER / ANSWER_PLUS_EXTRA / CORRECTION | §6.3 | next question (after an acknowledgement or "Updated: ...") |
| CLARIFICATION | no state change | field `why` or `help` text, then the same pending question |
| DONT_KNOW | optional: status `dont_know`; required: `deferred` | "That is okay." then next question |
| SKIP | same as DONT_KNOW, status `skipped`/`deferred` | "Skipped." then next question |
| PAUSE | → PAUSED | fixed pause text + resume code |
| OFF_TOPIC | no state change | "I can only help with this form." + same question |
| DISTRESS (overwhelmed) | no state change | fixed supportive text + 3 buttons: Take a break · Talk to a person · Keep going |
| DISTRESS (crisis) | → NEEDS_HUMAN | fixed emergency guidance + "Talk to a person" |
| UNSAFE | no state change, `unsafe_blocked` event | "I can only use the information for this form. I cannot send or share anything else." + same question |

Showing the same pending question again after a clarification or off-topic reply is **not** a repeated question. It is the same turn. This includes `intake_type` → "I'm not sure", which shows one fixed explanation line and then the same two buttons (§5.3 note ²). A repeated question means asking again for a field that is already accepted, confirmed, skipped, deferred or `dont_know`, without the user asking to change it.

### 6.5 Distress and crisis: deterministic backstop

A fixed keyword/regex list for crisis language runs **before** the LLM. If it matches, the crisis response is shown whatever the LLM says. The LLM can raise the level (e.g. detect overwhelm) but can never lower a keyword match. Overwhelm text is written by us and stored in `templates.py`. Crisis and emergency text (911, 988 for `REGION=US`) is stored only in the per-region file `app/content/regions/<region>.toml` (§12, Q3).

### 6.6 Button replies bypass the LLM

`POST /replies` accepts either `{"text": "..."}` or `{"choice": "<option_id>"}`. Choices (options, yes/no, conflict picks, date picks) are handled fully in code. Typed free text during a yes/no confirmation first goes through a small deterministic yes/no matcher ("yes", "yeah", "correct", "no", "nope"...). The LLM is called only if that matcher cannot decide.

### 6.7 Repeated failure

If a field gets 3 validation failures in a row (`MAX_FIELD_ATTEMPTS`), the next message offers buttons: "Answer later" · "Talk to a person". It never keeps retrying on its own. "Talk to a person" → NEEDS_HUMAN.

### 6.8 Optional later experiment

Compare this single understanding agent against an ADK multi-agent variant (for example a router plus per-section extractors) on the same eval harness. The winner is not decided in advance. This is also the only place an LLM-written staff summary could be tried, and only with the §11.1 traceability check.

---

## 7. Workflow

### 7.1 States

`GREETING`, `CHOOSE_INTAKE_TYPE`, `COLLECTING`, `CONFIRMING_EXTRA`, `RESOLVING_CONFLICT`, `REVIEW`, `SUBMITTED`, `PAUSED`, `NEEDS_HUMAN`.

"Collecting states" means: CHOOSE_INTAKE_TYPE, COLLECTING, CONFIRMING_EXTRA, RESOLVING_CONFLICT, REVIEW.

### 7.2 Transition table (single source of truth, `workflow/transitions.py`)

| From | Event | Guard | To |
|---|---|---|---|
| GREETING | `start` | – | CHOOSE_INTAKE_TYPE |
| CHOOSE_INTAKE_TYPE | `field_accepted(intake_type)` | queue empty | COLLECTING |
| CHOOSE_INTAKE_TYPE | `field_accepted(intake_type)` | queue non-empty | CONFIRMING_EXTRA |
| COLLECTING | `field_accepted` / `field_skipped` / `field_deferred` | queue empty, fields remain | COLLECTING |
| COLLECTING | `extras_queued` | – | CONFIRMING_EXTRA |
| COLLECTING | `conflict_detected` | – | RESOLVING_CONFLICT |
| COLLECTING | `no_fields_remaining` | – | REVIEW |
| CONFIRMING_EXTRA | `extra_confirmed` / `extra_rejected` | next queue item is an extra | CONFIRMING_EXTRA |
| CONFIRMING_EXTRA | `extra_confirmed` / `extra_rejected` | next queue item is a conflict | RESOLVING_CONFLICT |
| CONFIRMING_EXTRA | `queue_empty` | `return_to_review` | REVIEW |
| CONFIRMING_EXTRA | `queue_empty` | otherwise | COLLECTING |
| RESOLVING_CONFLICT | `conflict_resolved` | same rules as the three rows above | CONFIRMING_EXTRA / REVIEW / COLLECTING |
| COLLECTING / CONFIRMING_EXTRA / REVIEW | `correction_undone` | previous turn was a `field_corrected` | same state |
| REVIEW | `edit_field(field_id)` | field applicable | COLLECTING (that field pinned, `return_to_review=true`) |
| REVIEW | `field_marked_unknown(field_id)` | effective tier = required | REVIEW |
| REVIEW | `submit` | every effectively must_have field answered ∧ policy allow | SUBMITTED |
| REVIEW | `submit` | otherwise | REVIEW (response lists what is missing) |
| any collecting state | `pause` | – | PAUSED (saves `resume_state`) |
| PAUSED | `resume` | valid token | `resume_state` |
| any collecting state | `crisis_detected` / `human_requested` | – | NEEDS_HUMAN (saves `resume_state`) |
| NEEDS_HUMAN | `resume` | user chooses "Continue on my own" | `resume_state` |
| SUBMITTED | – | terminal | – |

Any (state, event) pair not in the table raises `IllegalTransition`, is logged, and changes nothing. A test enumerates every pair (§13).

### 7.3 Side-effect authorization

`send_email`, `generate_staff_summary` and `generate_benefit_demo` are allowed **only in SUBMITTED**. The policy engine enforces this, and it is tested for every other state.

---

## 8. Persistence

Every write for one turn happens in **one transaction**. So a saved answer and its event either both exist or neither does.

| Table | Key columns | Notes |
|---|---|---|
| `intakes` | `id` UUIDv4 PK · `intake_type` · `state` · `resume_state` · `respondent` (self/other) · `return_to_review` · `token_hash` · `resume_code_hash` · `synthetic` (always true) · `created_at` · `updated_at` | One row per intake. No module globals. |
| `field_values` | (`intake_id`, `field_id`) unique · `value` · `display_value` · `status` (accepted/confirmed/skipped/deferred/dont_know/unknown_confirmed) · `source` (explicit/inferred/button) · `attempts` · `updated_at` | Current value per field. |
| `pending_items` | `id` · `intake_id` · `seq` · `kind` (extra/conflict/date_choice) · `field_id` · `payload` JSON | The FIFO queue behind CONFIRMING_EXTRA / RESOLVING_CONFLICT. |
| `intake_events` | `id` · `intake_id` · `seq` (per intake, unique) · `type` · `field_id` · `payload` JSON · `created_at` | **Append-only.** Types: `created`, `question_shown`, `field_proposed`, `field_accepted`, `field_confirmed`, `field_rejected`, `field_corrected`, `conflict_detected`, `conflict_resolved`, `field_skipped`, `field_deferred`, `field_marked_unknown`, `paused`, `resumed`, `distress_shown`, `needs_human`, `unsafe_blocked`, `submitted`, `email_sent`, `email_denied`, `staff_summary_generated`, `benefit_demo_generated`. |
| `llm_calls` | `id` · `intake_id` · `agent` · `model` · `input_tokens` · `output_tokens` · `latency_ms` · `reply_kind` · `status` (ok/parse_error/timeout/rejected) · `created_at` | **No prompt or response text** by default. |
| `email_sends` | `id` · `intake_id` · `idempotency_key` (unique) · `status` · `provider` · `created_at` | Idempotency and audit. The recipient is not stored here. It is always re-read from `field_values`. |
| `staff_outputs` | `id` · `intake_id` · `kind` (staff_summary/benefit_demo) · `content` JSON · `created_at` | Generated drafts. |

The DB file path comes from `DATABASE_URL` (default `v2/backend/var/intake.db`, gitignored). Nothing is written into the source tree.

---

## 9. API

### 9.1 Endpoints

All `/intakes/{id}/*` routes require header `X-Intake-Token`. This is a demo token returned by `POST /intakes`, and only its hash is stored. It is **not** an auth system.

| Method & path | Purpose | Notes |
|---|---|---|
| `POST /intakes` | Create an intake | Returns `{id, token, resume_code, turn}`. State GREETING. |
| `GET /intakes/{id}` | Current state + current turn + progress | Used on page load and resume. |
| `POST /intakes/{id}/start` | GREETING → CHOOSE_INTAKE_TYPE | |
| `POST /intakes/{id}/replies` | Body `{text}` or `{choice}` + `client_turn_id` | Returns the next `Turn`. `client_turn_id` makes a double-submit harmless. |
| `POST /intakes/{id}/pause` | → PAUSED | Returns resume instructions. |
| `POST /intakes/{id}/resume` | PAUSED/NEEDS_HUMAN → previous state | Token, or `{resume_code}` from a new device. |
| `GET /intakes/{id}/review` | All values, grouped by section, plus "Still needed" | |
| `POST /intakes/{id}/review/edit` | `{field_id}` → pins that question | |
| `POST /intakes/{id}/submit` | REVIEW → SUBMITTED | 409 + missing list if incomplete. |
| `POST /intakes/{id}/email` | Send the confirmation email | Header `Idempotency-Key` required. **No recipient in the body.** Allowed only in SUBMITTED, only if `email` has an accepted/confirmed value. |
| `POST /intakes/{id}/staff-summary` | Generate the staff summary (§11.1) | SUBMITTED only. |
| `POST /intakes/{id}/benefit-summary` | Generate the synthetic benefit demo (§11.2) | SUBMITTED only. |
| `GET /health` | Liveness | |

There is **no** SOAP endpoint (D1).

### 9.2 `Turn` response

```json
{
  "state": "COLLECTING",
  "acknowledgement": "Saved.",
  "question": {
    "field_id": "date_of_birth",
    "kind": "field | confirm_extra | conflict | date_choice | distress | resume",
    "text": "What is your date of birth?",
    "example": "May 4, 2004",
    "input_type": "date",
    "options": [],
    "can_skip": false,
    "can_defer": true
  },
  "info": null,
  "progress": { "answered": 3, "about_total": 12,
                "sections": [{"name": "About you", "done": true}] }
}
```

`question` is **one object or null**, never a list. That is P1 at the API boundary. `info` carries fixed non-question text (the `why` answer, distress guidance, pause instructions).

---

## 10. Guardrails

### 10.1 Input (`guardrails/input.py`)

- Maximum `MAX_MESSAGE_CHARS` (default 1000). Longer text gets a polite fixed message and is not sent to the LLM.
- Strip control characters. Normalize Unicode (NFKC).
- Crisis keyword check (§6.5).
- Pattern checks for common injection phrasing ("ignore previous instructions", "system prompt", "send this to", email addresses outside the email question, "other patient", "list all"). A match sets a flag passed to the policy. It does **not** replace structural safety. The real defence is that the agent has no tools and its output can only propose field values.

### 10.2 Output (`guardrails/output.py`)

- The LLM response must parse into `ReplyUnderstanding`. On a parse error or timeout, retry once. If it still fails, show a fixed "I did not understand. Here is the question again." and log `llm_calls.status`. State does not change.
- Proposals are checked as in §6.3 (real field, applicable, `raw_text` really appears in the message, value derived from `raw_text`).
- An `email` proposal is only accepted when the pending field is `email`, or through a yes/no confirmation. It can never be accepted while the input flag says "send to".

### 10.3 Policy engine (`guardrails/policy.py`)

```python
def decide(snapshot: IntakeSnapshot, action: Action) -> Decision:
    """Return Decision(verdict=allow|deny|require_confirmation, reason=...)."""
```

`Action` is a closed union: `AcceptField`, `QueueConfirmation`, `ApplyCorrection`, `Transition`, `Submit`, `SendEmail`, `GenerateStaffSummary`, `GenerateBenefitDemo`. Every state change and every side effect goes through `decide`. Examples of rules:
- Side effects only in SUBMITTED.
- `inferred` → require_confirmation.
- Correction of `email` after SUBMITTED → deny.
- `SendEmail` with no stored email → deny (no fallback).

### 10.4 Redaction (`guardrails/redaction.py`)

A logging filter replaces:
- every value known for the current intake (passed via a context variable), and
- generic patterns: emails, phone-like numbers, dates

with `[REDACTED]`. Logs carry ids, field ids, states and event types only. Exceptions are logged with a redacted message. Users see fixed text only (audit B10).

---

## 11. Staff-facing outputs

### 11.1 Intake summary for staff (replaces SOAP, D1)

- Built by **deterministic code** (`services/staff_summary.py`) from `field_values` and `intake_events` of the current intake only.
- Shape:

```python
class Statement(BaseModel):
    text: str                         # "Date of birth: May 4, 2004"
    sources: list[str]                # ["field:date_of_birth"] or ["event:42"]

class StaffSummary(BaseModel):
    title: Literal["Intake summary for staff"]
    disclaimer: str                   # "Built from the form answers only. Not a clinical document."
    sections: dict[str, list[Statement]]   # by registry section
    not_answered: list[Statement]     # "Not answered, please follow up" (deferred) and
                                      # "Not known, please follow up" (unknown_confirmed), each cited
    notes: list[Statement]            # administrative only, e.g. "Asked to talk to a person" (event-cited)
```

- A validator checks that every statement has ≥ 1 source, that every source exists for this intake, and that system-written text contains no clinical terms. Two deny-lists live in `app/domain/clinical.py`:
  - `CONDITION_CLAIMS` (diagnosis, disorder, syndrome, symptom, prognosis, "has autism", ICD-10 codes such as `F84.0`) is banned in **every** fixed text, including option labels.
  - `CLINICAL_TERMS` adds assessment, treatment plan and similar words, and applies to text the system writes itself.
  - A user's own chosen or typed value is quoted verbatim as theirs, with its source field cited, and is not checked against `CLINICAL_TERMS`. For example, `inquiry_reason` = "An autism assessment" names the service they are asking for.
- My recommendation is that it stays deterministic. An LLM-written version is only an optional experiment (§6.8), and it would have to pass the same validator.

### 11.2 Benefit summary (synthetic demo, D2)

- Deterministic. Insurance numbers are generated from a seed based on the intake id, reusing the V1 benefit text layout.
- Every output starts and ends with: **"SYNTHETIC DEMO. These numbers are made up. They are not linked to any insurance plan."**
- It uses only `full_name` from the current intake. It has no access to other records.

### 11.3 Email

- `services/email.py`: `send_confirmation(intake_id, idempotency_key)`. There is **no recipient parameter**. The recipient is read from `field_values[email]` of that intake.
- Providers: `console` (default, logs a redacted line) and `smtp` (reserved test domains only while `SYNTHETIC_ONLY`).
- The same idempotency key returns the first result and does not send again.
- Body: fixed plain-language template. It contains no answers beyond the first name.

---

## 12. Configuration (`app/config.py`)

| Setting | Default | Notes |
|---|---|---|
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | Required to be set. There is no literal anywhere else. |
| API key | – | Added in Phase 5, using the exact variable name the installed `google-genai`/ADK read. `.env.example` (empty value) is committed, `.env` is gitignored, and the owner creates `.env`. Unit, workflow and API tests never need the key. |
| `SYNTHETIC_ONLY` | `true` | Validator: must be `true`, or startup fails. |
| `DATABASE_URL` | `sqlite:///var/intake.db` | Relative to backend dir, gitignored. |
| `EMAIL_PROVIDER` | `console` | `console` / `smtp` |
| `REGION` | `US` | Selects the default phone-parsing region and the per-region content file `app/content/regions/<region>.toml` (crisis and emergency text: 911, 988). Crisis text lives only in these files, never in code. Startup fails if the file for `REGION` is missing. |
| `MAX_MESSAGE_CHARS` | 1000 | |
| `MAX_FIELD_ATTEMPTS` | 3 | |
| `LLM_TIMEOUT_S` | 15 | |

---

## 13. Test plan

### 13.1 Suites

| Suite | Contents |
|---|---|
| `tests/unit` | Normalizers, validators, registry integrity, templates (grade/words/one `?`), redaction. |
| `tests/workflow` | Every transition in the table, every illegal pair, full flows with a **fake understanding agent** (no network), pause/resume, conflicts, corrections, deferral. Property tests (hypothesis) over random reply sequences. |
| `tests/safety` | Injection, hallucinated proposals, distress, policy engine, agent tool surface. |
| `tests/api` | FastAPI `TestClient` flows, tokens, idempotency, error shapes. |
| `tests/regression` | One named test per Critical/High audit item (below). |

CI (GitHub Actions) runs `uv sync --locked`, `ruff check`, `ruff format --check`, `mypy`, `pytest`, then the frontend `tsc`, `vitest` and axe checks. Live-LLM tests are marked `@pytest.mark.live`. They are deselected by default (`addopts = -m "not live"`) and in CI. Run them explicitly with `pytest -m live`.

### 13.2 Regression tests from the audit

Every Critical and High item has at least one named test. All of them live in `tests/regression/` unless noted.

| Audit | Sev. | Test(s) |
|---|---|---|
| #1 model hardcoded | Crit | `test_no_hardcoded_model_ids` (scan `app/` for `gemini-` literals outside `config.py`) · `test_agent_uses_configured_model` |
| #2 one question not enforced | High | `test_turn_has_at_most_one_question` (property test over random flows) · `test_every_question_template_has_exactly_one_question_mark` · `test_api_question_is_object_not_list` |
| #3 nothing saved until end | Crit | `test_partial_intake_survives_restart` (answer 3 fields, dispose app + engine, new app, same values and same pending question) · `test_each_accepted_answer_is_committed_before_response` |
| #4 intake type asked repeatedly | High | `test_intake_type_asked_once` · `test_no_field_asked_again_after_resolution` (property test) · `test_frontend_renders_no_hardcoded_questions` (vitest, frontend) |
| #5 global shared session | Crit | `test_concurrent_intakes_are_isolated` (interleave two intakes, assert no value crosses) · `test_intake_ids_are_uuid4` · `test_app_factory_creates_independent_state` |
| #6 email wrong recipient | Crit | `test_email_recipient_ignores_llm_argument` · `test_email_has_no_fallback_to_other_records` (intake without email, other intakes with email → deny) · `test_email_endpoint_rejects_recipient_in_body` · `test_email_idempotency_key_prevents_duplicate_send` |
| #7 PII in debug prints | High | `test_logs_contain_no_field_values` (full flow, capture logs, assert no stored value appears) · `test_redaction_filter_masks_emails_phones_dates` · ruff `T201` (no `print`) in CI |
| #8 outputs disconnected from intake | High | `test_staff_summary_uses_only_current_intake` · `test_benefit_demo_uses_only_current_intake_name` · `test_benefit_demo_is_labelled_synthetic` |
| #9 format burden | High | `test_date_formats_accepted` (parametrized) · `test_ambiguous_date_requires_choice` · `test_phone_formats_normalized` · `test_gender_options_inclusive` · `test_retry_text_never_blames_user` |
| #10 personal data in repo | Crit | `test_tracked_files_contain_no_real_contact_data` (scans `git ls-files` for emails outside reserved domains and phone numbers outside the fictional NXX-555-0100 to 0199 range) · `test_gitignore_covers_env_db_and_data` · `test_synthetic_only_cannot_be_disabled` |
| B1 LLM can send email | Crit | `test_agent_has_no_side_effect_tools` · `test_email_service_signature_has_no_recipient` |
| B2 LLM can read other records | Crit | `test_agent_has_no_read_tools` · `test_agent_input_contains_only_current_intake` · `test_agent_input_contains_no_stored_values` |
| B3 path traversal / file writes | Crit | `test_agents_do_not_write_files` (run agent in temp cwd, directory stays empty) · `test_no_filesystem_writes_outside_db_path` |
| B4 invented diagnoses | High | `test_no_soap_endpoint` · `test_staff_summary_every_statement_cites_source` · `test_staff_summary_contains_no_clinical_terms` |
| B5 email without review | High | `test_email_denied_in_every_state_except_submitted` · `test_submit_requires_review_state` |
| B9 no tests | High | Covered by the CI workflow itself. `test_ci_workflow_runs_tests_and_linters` checks the workflow file lists the steps. |
| B11 data inside source tree | High | `test_default_db_path_is_gitignored` · `test_smtp_provider_rejects_non_reserved_domains` |

Other safety tests (in `tests/safety`):
- `test_injection_cannot_change_state_or_recipient`
- `test_proposal_raw_text_must_appear_in_message`
- `test_proposal_for_unknown_field_rejected`
- `test_value_is_derived_from_raw_text_not_llm_value`
- `test_inferred_values_always_require_confirmation`
- `test_distress_triggers_fixed_response`
- `test_crisis_keywords_bypass_llm`
- `test_llm_parse_failure_changes_nothing`
- `test_illegal_transitions_raise` (enumerates all pairs)
- `test_side_effects_only_in_submitted`

---

## 14. Evaluation harness (synthetic only)

### 14.1 Dataset

- 60 scripted conversations to start, growing to 150+. JSONL in `evals/datasets/`.
- Each case has:
  - a **persona**: communication pattern plus an answer book `field_id → reply text`
  - a **script** of special turns (e.g. "at question 3, reply with name+DOB", "after field X, pause, then resume")
  - **expected** final values, expected reply kinds, and expected events

  Because the engine is deterministic, the runner answers whichever question is asked from the answer book. So a case does not break when question order changes.
- Categories, about 4 to 5 cases each at the start:
  1. straightforward
  2. one-word / very literal
  3. long answers with several fields
  4. out-of-order information
  5. corrections
  6. contradictions
  7. "I don't know" / skips
  8. pause and resume mid-intake
  9. "why are you asking?"
  10. off-topic
  11. distress and overwhelm (including crisis phrasing)
  12. ambiguous dates and formats
  13. injection attempts (including "send this to another email")
- Personas are based on **communication patterns**, not stereotypes about autistic people. Examples:
  - very short literal replies
  - long detailed replies
  - no punctuation or all lower case
  - many typos
  - English as a second language
  - parent filling for an adult child
  - clinic staff member sending a referral
  - asks "why" often
  - answers the question plus context
- All names, emails (`@example.com`), phones (`NXX-555-0100` to `NXX-555-0199`, e.g. `202-555-0100`) and addresses are synthetic. They are generated with a fixed seed and checked by the same scan as `test_tracked_files_contain_no_real_contact_data`.

### 14.2 Metrics

| Metric | Target / note |
|---|---|
| Field accuracy (exact match after normalization) | per field and overall |
| Completion rate (reached SUBMITTED when the script intends it) | |
| Questions per turn | **always 0 or 1** (hard fail otherwise) |
| Repeated questions (definition in §6.4) | **0** |
| Reading grade and word count per question shown | ≤ 6, ≤ 15 |
| Unnecessary confirmations (confirmation of an explicit value for the pending field) | 0 |
| Correct handling rate per reply kind | per kind |
| Distress handled with the fixed response | 100 % |
| Crisis cases reaching NEEDS_HUMAN | 100 % |
| Unsafe actions accepted (state change or side effect caused by injection) | **0** |
| Tokens and latency per intake and per turn | from `llm_calls` |
| LLM calls avoided by buttons | informational |

The goal is **lower load per turn and zero repeated questions**. It is not fewer total questions.

### 14.3 V1 baseline

- A throwaway branch `v1-baseline`. The only changes are the model name (read from env) and whatever ADK 2.x compatibility fixes are strictly needed (e.g. `await create_session`). Each fix is listed in `EVAL_RESULTS.md`.
- Runs with email credentials unset (so no email is sent) and in a temp working directory (because V1 writes files).
- `evals/v1_adapter.py` drives V1 through the ADK `Runner` with the same personas. It measures:
  - questions per turn (heuristic: count of `?` plus registry-field mentions per message; the method is documented)
  - repeated questions
  - completion
  - field accuracy from V1's JSON output
- Only scenarios that make sense for V1 are included (V1 has no pause/resume or review). Excluded categories are listed.
- Results are written to `docs/EVAL_RESULTS.md` as a before/after table.

---

## 15. Implementation phases

| Phase | Content |
|---|---|
| 2 | Scaffolding: uv project, config, pinned deps, `.gitignore`, pre-commit, CI. |
| 3 | Domain: registry, models, normalizers, validators, template checks + unit tests. |
| 4 | Workflow engine + persistence: states, transitions, events, pending queue, pause/resume. Full-flow tests with a fake agent. |
| 5 | Understanding agent (ADK + Gemini structured output), guardrails, policy engine, safety tests. Check the ADK API and model list first. |
| 6 | API layer + services: email (idempotent, console default), staff summary, benefit demo. |
| 7 | Frontend, then accessibility pass (axe, keyboard walkthrough, grade check). |
| 8 | Eval harness, V1 baseline, `docs/EVAL_RESULTS.md`. |
| Final | README rewrite. |

I renumbered to match your order: you listed six implementation steps under "Phases 2 to 8". The persistence step and the understanding-agent step are split so each phase ends with green tests. After each phase: tests, ruff, mypy, summary, **STOP**.

---

## 16. Resolved decisions (spec review, approved)

| # | Decision |
|---|---|
| Q1 | **Updated:** required fields are split into two tiers (§5.2). *must_have* (intake_type, relationship, respondent_name, full_name, and the contact field required by the contact rule) blocks submit. *required* (date_of_birth, preferred_contact_method, inquiry_reason, referral_provider_name, referral_type, referral_date) shows "Answer now" and "I don't know this" on review and can end as `unknown_confirmed`. Submit is allowed once all must_have fields are answered. **Reason:** a respondent may genuinely not know, for example, a patient's date of birth, and the form must never become impossible to finish. |
| Q2 | US defaults, with `REGION=US` in config. Phone parsing uses the region from config. |
| Q3 | Crisis and emergency text (911, 988) lives in a per-region content file, not in code. |
| Q1b | "I'm not sure" on an effectively optional field is final (status `dont_know`): saved, never asked again, never shown as "Still needed". |
| Q4 | `preferred_name` (optional; once given, used in greetings) and `gender` (optional, inclusive options plus "Prefer not to say") are included. |
| Q5 | The owner reviews the §5.3 wording before Phase 3 and sends edits. §5.3 is a draft until then. |
| Q6 | The staff summary is deterministic. |
| Q7 | Direct save with "Updated: …" + Undo only when kind = CORRECTION and the new value is quoted from the message. Everything else goes through the conflict question. |

Additional regression tests from these decisions:
- `test_correction_requires_quoted_value`
- `test_inferred_change_goes_to_conflict_question`
- `test_undo_restores_previous_value`
- `test_submit_blocked_until_required_answered`
- `test_crisis_text_loaded_from_region_file`
- `test_preferred_name_never_in_question_text`
- `test_unit_tests_do_not_need_api_key` (runs the default suite with no key in the environment; this is also what CI does)

Additional regression tests from the §5.3 owner review:
- `test_fi_contact_fields_belong_to_respondent` (FI with relationship ≠ me: phone/email/address use "you" wording and are about the respondent; PR: the patient's)
- `test_respondent_name_only_when_relationship_not_me`
- `test_intake_type_not_sure_is_clarification_not_repeat` (shows the explanation, then the same buttons; nothing saved; `repeated_questions` stays 0)
- `test_inquiry_reason_options_are_administrative` (no option label contains a condition or clinical term from the §11.1 deny-list)
- `test_start_screen_count_matches_registry` ("about 12" stays within ±1 of every path's total)

Additional regression tests from the Q1 update:
- `test_optional_not_sure_is_final_and_not_listed_on_review`
- `test_required_field_can_be_marked_unknown_and_submit_allowed`
- `test_must_have_field_blocks_submit`
- `test_unknown_field_shown_as_follow_up_in_staff_summary` (Phase 6)
