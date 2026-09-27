import { useEffect, useState } from "react";
import { loadTextScale, saveTextScale } from "../storage";
import { useText } from "../text";

const SCALES = [1, 1.15, 1.3, 1.5, 1.75];

/** Bigger or smaller text for the whole page. Remembered on this device. */
export function TextSize() {
  const text = useText();
  const [scale, setScale] = useState(() => {
    const saved = loadTextScale();
    return SCALES.includes(saved) ? saved : 1;
  });
  useEffect(() => {
    document.documentElement.style.fontSize = `${scale * 100}%`;
    saveTextScale(scale);
  }, [scale]);
  const index = SCALES.indexOf(scale);
  return (
    <div className="text-size" role="group" aria-label={text.labels.text_size}>
      <button
        type="button"
        className="secondary"
        disabled={index <= 0}
        onClick={() => setScale(SCALES[index - 1] ?? scale)}
      >
        {text.labels.text_smaller}
      </button>
      <button
        type="button"
        className="secondary"
        disabled={index >= SCALES.length - 1}
        onClick={() => setScale(SCALES[index + 1] ?? scale)}
      >
        {text.labels.text_bigger}
      </button>
    </div>
  );
}
