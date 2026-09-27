import type { ResumeCodeView, TurnView } from "../api/client";
import { useText } from "../text";
import { CodeBox } from "./CodeBox";

interface Props {
  view: TurnView;
  code: ResumeCodeView | null;
  onSkip: () => void;
  onBreak: () => void;
  onShowCode: () => void;
}

/** The fixed bar under every question: the same buttons in the same places, every time.
 * Left: "Skip" or "Answer later" (a placeholder keeps the place when neither applies).
 * Right: "Take a break" and "Show my code" (the Take a break area). */
export function Bar({ view, code, onSkip, onBreak, onShowCode }: Props) {
  const text = useText();
  const q = view.question?.kind === "field" ? view.question : null;
  const skipLabel = q?.can_skip ? text.buttons.skip : q?.can_defer ? text.buttons.answer_later : null;
  return (
    <div className="bar-area">
      <div className="bar">
        <div className="bar-left">
          {skipLabel ? (
            <button type="button" className="secondary" onClick={onSkip}>
              {skipLabel}
            </button>
          ) : (
            <span className="bar-placeholder" />
          )}
        </div>
        <div className="bar-right">
          <button type="button" className="secondary" onClick={onBreak}>
            {text.buttons.take_a_break}
          </button>
          <button type="button" className="secondary" onClick={onShowCode}>
            {text.labels.show_code}
          </button>
        </div>
      </div>
      {code && <CodeBox code={code.resume_code} info={code.info} />}
    </div>
  );
}
