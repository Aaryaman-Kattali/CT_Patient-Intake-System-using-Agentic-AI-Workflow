import { useId, useState, type FormEvent, type RefObject } from "react";
import type { ActionView } from "../api/client";
import { useText } from "../text";
import { HEADING_ID } from "./TurnScreen";

interface Props {
  headingRef: RefObject<HTMLHeadingElement | null>;
  message: string | null; // the API's fixed answer to a failed attempt
  actions: ActionView[]; // e.g. "Talk to a person" when locked out
  help: string[]; // shown after "Talk to a person"
  onSend: (code: string) => void;
  onAction: (actionId: string) => void;
  onBack: () => void;
}

/** Come back on this or another device with the code. Case, spaces and dashes do not matter. */
export function EnterCode({ headingRef, message, actions, help, onSend, onAction, onBack }: Props) {
  const text = useText();
  const id = useId();
  const [code, setCode] = useState("");
  const send = (event: FormEvent) => {
    event.preventDefault();
    if (code.trim()) onSend(code);
  };
  return (
    <>
      <h1 id={HEADING_ID} ref={headingRef} tabIndex={-1}>
        {text.labels.enter_code}
      </h1>
      <p>{text.sentences.resume_intro}</p>
      <form className="text-answer" onSubmit={send}>
        <label htmlFor={id}>{text.labels.your_code}</label>
        <input
          id={id}
          type="text"
          autoCapitalize="characters"
          autoComplete="off"
          spellCheck={false}
          value={code}
          onChange={(e) => setCode(e.target.value)}
        />
        <button type="submit">{text.buttons.resume}</button>
      </form>
      {message && <p className="notice">{message}</p>}
      {actions.map((action) => (
        <button key={action.id} type="button" onClick={() => onAction(action.id)}>
          {action.label}
        </button>
      ))}
      {help.length > 0 && (
        <div className="info">
          {help.map((line, i) => (
            <p key={i}>{line}</p>
          ))}
        </div>
      )}
      <div className="actions">
        <button type="button" className="secondary" onClick={onBack}>
          {text.labels.back}
        </button>
      </div>
    </>
  );
}
