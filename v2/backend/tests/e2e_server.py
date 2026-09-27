"""The real API with a scripted understander, for the frontend's Playwright tests.

No network, no API key: typed replies are read by simple rules, not by Gemini.
Run: uv run python -m tests.e2e_server --port 8001 --origin http://localhost:5173

Rules for typed text (synthetic test data only):
- "why ..." asks why the question is asked; "too much ..." is distress (overwhelmed).
- "I don't know" is dont_know.
- "slow: <text>" waits 1.5 s first (to see the "Reading your answer" status), then reads <text>.
- Otherwise the text before the first ";" answers the question being asked, and every
  "field_id=value" part after it proposes an extra value (so conflicts and confirmations
  can be reached): "Alex Rivera; date_of_birth=May 4 2004".
"""

import argparse
import os
import secrets
import tempfile
import time
from pathlib import Path

import uvicorn

from app.config import Settings
from app.main import create_app
from app.workflow.understanding import (
    AgentReply,
    FieldProposal,
    LlmCallInfo,
    ReplyKind,
    ReplyUnderstanding,
    UnderstandingContext,
)

CALL = LlmCallInfo(model="e2e-rules", input_tokens=0, output_tokens=0, latency_ms=0, status="ok")


def _proposal(field_id: str, raw: str) -> FieldProposal:
    return FieldProposal(field_id=field_id, raw_text=raw, value=raw, source="explicit")


class RuleUnderstander:
    def understand(self, message: str, context: UnderstandingContext) -> AgentReply:
        if message.casefold().startswith("slow:"):
            time.sleep(1.5)
            message = message[len("slow:") :]
        return AgentReply(understanding=self._read(message, context), call=CALL)

    @staticmethod
    def _read(message: str, context: UnderstandingContext) -> ReplyUnderstanding:
        low = message.strip().casefold()
        if low.startswith("why"):
            return ReplyUnderstanding(kind=ReplyKind.CLARIFICATION, clarification="why")
        if low.startswith("too much"):
            return ReplyUnderstanding(kind=ReplyKind.DISTRESS, distress_level="overwhelmed")
        if low in ("i don't know", "i do not know"):
            return ReplyUnderstanding(kind=ReplyKind.DONT_KNOW)
        first, *rest = [part.strip() for part in message.split(";")]
        proposals = []
        if first and context.pending is not None:
            proposals.append(_proposal(context.pending.id, first))
        for part in rest:
            field_id, _, raw = part.partition("=")
            if raw:
                proposals.append(_proposal(field_id.strip(), raw.strip()))
        kind = ReplyKind.ANSWER_PLUS_EXTRA if rest else ReplyKind.ANSWER
        return ReplyUnderstanding(kind=kind, proposals=tuple(proposals))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--origin", default="http://localhost:5173")
    args = parser.parse_args()
    os.environ.setdefault("APP_SECRET", secrets.token_hex(32))
    work = Path(tempfile.mkdtemp(prefix="intake-e2e-"))
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{(work / 'e2e.db').as_posix()}",
        email_provider="file",
        email_outbox_dir=work / "outbox",
        frontend_origin=args.origin,
        # Every test connects from 127.0.0.1; the lockout is tested with the per-code limit.
        resume_max_failures_per_client=1000,
    )
    app = create_app(settings, understander=RuleUnderstander())
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
