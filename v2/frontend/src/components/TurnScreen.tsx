import { useState, type RefObject } from "react";
import type { ReplyCommand, TurnView } from "../api/client";
import { fill, useText } from "../text";
import { Answer } from "./Answer";
import { CodeBox } from "./CodeBox";
import { Review } from "./Review";

export const HEADING_ID = "page-heading";

/** Actions shown in the fixed bar at the bottom, not with the other buttons. */
const BAR_ACTIONS = new Set(["take_a_break", "answer_later"]);

/** The page heading: the question when there is one; otherwise the first line of text. */
export function headingOf(view: TurnView, reviewTitle: string): { heading: string; rest: string[] } {
  if (view.question) return { heading: view.question.text, rest: view.info };
  if (view.state === "review") return { heading: reviewTitle, rest: view.info };
  return { heading: view.info[0] ?? "", rest: view.info.slice(1) };
}

interface Props {
  view: TurnView;
  headingRef: RefObject<HTMLHeadingElement | null>;
  onCommand: (command: ReplyCommand) => void;
  onAction: (actionId: string) => void;
  onEdit: (fieldId: string) => void;
}

export function TurnScreen({ view, headingRef, onCommand, onAction, onEdit }: Props) {
  const text = useText();
  const { heading, rest } = headingOf(view, text.labels.review_title ?? "");
  const question = view.question;
  const actions = view.actions.filter((a) => !BAR_ACTIONS.has(a.id));
  return (
    <>
      {view.acknowledgement && <p className="acknowledgement">{view.acknowledgement}</p>}
      <h1 id={HEADING_ID} ref={headingRef} tabIndex={-1}>
        {heading}
      </h1>
      {question && <Why key={`${view.turn}-${question.field_id}`} why={question.why} />}
      {rest.length > 0 && (
        <div className="info">
          {rest.map((line, i) => (
            <p key={i}>{line}</p>
          ))}
        </div>
      )}
      {view.state === "paused" && view.resume_code && <CodeBox code={view.resume_code} />}
      {question && (
        <Answer
          key={`${view.turn}-${question.field_id}-${question.kind}`}
          question={question}
          headingId={HEADING_ID}
          onCommand={onCommand}
        />
      )}
      {view.review && <Review review={view.review} onEdit={onEdit} onCommand={onCommand} />}
      {actions.length > 0 && (
        <div className="actions">
          {actions.map((action) => (
            <button key={action.id} type="button" onClick={() => onAction(action.id)}>
              {action.label}
            </button>
          ))}
        </div>
      )}
    </>
  );
}

/** "Why are you asking this?" always sits right under the question. */
function Why({ why }: { why: string }) {
  const text = useText();
  const [open, setOpen] = useState(false);
  return (
    <div className="why">
      <button
        type="button"
        className="link"
        aria-expanded={open}
        aria-controls="why-text"
        onClick={() => setOpen(!open)}
      >
        {text.buttons.why}
      </button>
      {open && (
        <p id="why-text" className="why-text">
          {why}
        </p>
      )}
    </div>
  );
}

export function Progress({ view }: { view: TurnView }) {
  const text = useText();
  const { answered, about_total, sections } = view.progress;
  const number = Math.min(answered + 1, about_total);
  return (
    <nav className="progress" aria-label={text.labels.progress ?? ""}>
      {view.question && (
        <p>{fill(text.sentences.progress ?? "", { number, total: about_total })}</p>
      )}
      <ol>
        {sections.map((s) => (
          <li key={s.name} className={s.done ? "done" : undefined}>
            {s.name}
            {s.done && <span className="visually-hidden">: {text.labels.done}</span>}
            {s.done && <span aria-hidden="true"> ✓</span>}
          </li>
        ))}
      </ol>
    </nav>
  );
}
