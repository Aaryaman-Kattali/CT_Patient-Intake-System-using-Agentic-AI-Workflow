import { useText } from "../text";

interface Props {
  onEmail: () => void;
  onNewForm: () => void;
}

/** After sending: only what the patient needs. Staff drafts live on a separate page. */
export function AfterSubmit({ onEmail, onNewForm }: Props) {
  const text = useText();
  return (
    <div className="actions">
      <button type="button" onClick={onEmail}>
        {text.labels.email_me}
      </button>
      <button type="button" className="secondary" onClick={onNewForm}>
        {text.labels.new_form}
      </button>
    </div>
  );
}
