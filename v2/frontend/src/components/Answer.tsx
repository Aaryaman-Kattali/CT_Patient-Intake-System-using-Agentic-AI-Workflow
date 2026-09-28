import { useId, useState, type FormEvent } from "react";
import type { QuestionView, ReplyCommand } from "../api/client";
import { fill, useText } from "../text";

const NOT_SURE = "not_sure";

/** "I'm not sure" is always the last option button, wherever the data puts it. */
export function orderedOptions(question: QuestionView): QuestionView["options"] {
  return [
    ...question.options.filter((o) => o.id !== NOT_SURE),
    ...question.options.filter((o) => o.id === NOT_SURE),
  ];
}

interface Props {
  question: QuestionView;
  headingId: string;
  onCommand: (command: ReplyCommand) => void;
}

/** The answer area: buttons for choices and yes/no questions, a text box for typed answers. */
export function Answer({ question, headingId, onCommand }: Props) {
  if (question.input_type === "choice") {
    return <Choices question={question} headingId={headingId} onCommand={onCommand} />;
  }
  return <TypedAnswer question={question} onCommand={onCommand} />;
}

function Choices({ question, headingId, onCommand }: Props) {
  const [freeText, setFreeText] = useState<string | null>(null);
  const free = question.options.find((o) => o.id === freeText);
  return (
    <div className="answer">
      <div className="options" role="group" aria-labelledby={headingId}>
        {orderedOptions(question).map((option) => (
          <button
            key={option.id}
            type="button"
            className="option"
            aria-expanded={option.free_text ? freeText === option.id : undefined}
            onClick={() =>
              option.free_text
                ? setFreeText(option.id)
                : onCommand({ kind: "choose", option_id: option.id })
            }
          >
            {option.label}
          </button>
        ))}
      </div>
      {free && (
        <TextBox
          label={free.label}
          onSend={(text) => onCommand({ kind: "choose", option_id: free.id, extra_text: text })}
        />
      )}
    </div>
  );
}

function TypedAnswer({ question, onCommand }: Omit<Props, "headingId">) {
  const text = useText();
  return (
    <div className="answer">
      <TextBox
        label={text.labels.answer_box ?? ""}
        example={question.example ? fill(text.sentences.example ?? "", { example: question.example }) : undefined}
        inputMode={question.input_type === "email" ? "email" : question.input_type === "phone" ? "tel" : "text"}
        autoComplete={question.autocomplete}
        onSend={(value) => onCommand({ kind: "text", text: value })}
      />
    </div>
  );
}

interface TextBoxProps {
  label: string;
  example?: string;
  inputMode?: "text" | "email" | "tel";
  /** From the backend: a token only for details about the person typing, otherwise "off". */
  autoComplete?: string;
  onSend: (value: string) => void;
}

function TextBox({ label, example, inputMode = "text", autoComplete = "off", onSend }: TextBoxProps) {
  const text = useText();
  const id = useId();
  const [value, setValue] = useState("");
  const send = (event: FormEvent) => {
    event.preventDefault();
    if (value.trim()) onSend(value.trim());
  };
  return (
    <form className="text-answer" onSubmit={send}>
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        type="text"
        inputMode={inputMode}
        autoComplete={autoComplete}
        value={value}
        aria-describedby={example ? `${id}-example` : undefined}
        onChange={(e) => setValue(e.target.value)}
      />
      {example && (
        <p id={`${id}-example`} className="example">
          {example}
        </p>
      )}
      <button type="submit">{text.labels.send}</button>
    </form>
  );
}
