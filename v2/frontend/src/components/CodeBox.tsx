import { useState } from "react";
import { useText } from "../text";

/** The resume code, large and easy to copy down. */
export function CodeBox({ code, info = [] }: { code: string; info?: string[] }) {
  const text = useText();
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
    } catch {
      setCopied(false); // copying is a convenience; the code stays on screen to write down
    }
  };
  return (
    <div className="code-box">
      {info.map((line, i) => (
        <p key={i}>{line}</p>
      ))}
      <p className="code-label">{text.labels.your_code}</p>
      <p className="code" aria-label={code.split("").join(" ")}>
        {code}
      </p>
      <button type="button" className="secondary" onClick={() => void copy()}>
        {text.labels.copy_code}
      </button>
      <p role="status" className="copied">
        {copied ? text.sentences.code_copied : ""}
      </p>
    </div>
  );
}
