# CLAUDE.md

Hospital intake assistant for autistic patients and people filling forms for them.
- `agentic-ai/` is V1, an internship exercise built to a prescribed spec. It is a **reference only**: do not modify it.
- `v2/` is the redesign. Its full spec is `docs/V2_SPEC.md`, and the V1 findings are in `docs/V1_AUDIT.md`.

## Design principles (non-negotiable)

1. **One question per turn.** Every assistant message asks at most one thing. This is enforced in code: the workflow engine emits exactly zero or one pending question. It is not a prompt instruction.
2. **The system decides, the LLM interprets.** A deterministic workflow engine picks the next question from the field registry. The LLM never decides question order, when the intake is complete, or whether to send an email.
3. **Predictable, fixed wording.** Question text comes from the field registry as fixed, reviewed plain-language templates. The LLM never rephrases questions. It only understands replies. "Why are you asking this?" uses fixed per-field text.
4. **Save after every answer.** Each accepted answer is saved immediately as an event. The user can leave at any time and resume exactly where they were.
5. **Tolerate more, ask less.** Extract extra information from a reply, but never silently accept it. Confirm each extra value with a yes/no question, one per turn. Then skip the questions it already answered.
6. **Never pressure.** No timers, no hurry, no guilt. "I don't know" and "skip" are valid for non-required fields. Required fields can be deferred, and the review screen shows what is missing.
7. **Agents propose, the application decides.** All LLM output is structured (Pydantic via Gemini structured output), validated, and passed through the policy engine before it changes state or triggers a side effect. No LLM confidence scores; use provenance (explicit vs inferred).
8. **Side effects are services, not agents.** Email is a plain service called by the workflow after the user approves the review. The recipient always comes from validated stored state, never from LLM arguments. There is no fallback to other records.
9. **Administrative, not clinical.** Never diagnose, suggest conditions, or infer medical facts. Staff outputs are labelled drafts built only from stored data. There is no SOAP note.

## Agent rules

- No agent has side-effect tools.
- No agent has tools that read records other than the current intake. That data is passed in by the application, not fetched by the agent.
- No agent writes files.

## Working rules

- **Synthetic data only.** Never process or commit real personal or health data. `SYNTHETIC_ONLY` must stay `true`. Test data uses `@example.com` emails and phone numbers in the range `NXX-555-0100` to `NXX-555-0199` (e.g. `202-555-0100`). The PII scan test enforces the same rule.
- **Model IDs** come from `GEMINI_MODEL` in config, never from literals in code. Check the current Gemini model list and the installed ADK API before writing agent code.
- **Libraries:** use `google-genai`, not the deprecated `google-generativeai`. Do not add LangChain, LangGraph, RAG or vector DBs without a concrete, stated requirement. Prefer boring solutions.
- **Plain language:** user-facing text has a reading grade of 6 or lower, 15 words or fewer per question, and exactly one `?`. No idioms, no blame, no exclamation marks.
- **Checks:** when a wording or quality check fails, fix the content. Never loosen a threshold without the owner's approval.
- **Code style:** keep functions small and typed. Run `ruff`, `mypy` and `pytest` before calling a phase done. Do not use `print`; use the redacting logger.
- **Process:** work in phases and stop at each checkpoint for approval. Ask about unclear product decisions instead of guessing.
- **Git:** never rewrite git history or force-push without explicit approval. This checkout needs `git -c safe.directory=...`; do not change the global git config.
