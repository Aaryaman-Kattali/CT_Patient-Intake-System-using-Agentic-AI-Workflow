import type { ReplyCommand, ReviewView } from "../api/client";
import { useText } from "../text";

interface Props {
  review: ReviewView;
  onEdit: (fieldId: string) => void;
  onCommand: (command: ReplyCommand) => void;
}

/** All answers grouped by section, then what is still needed. Nothing is sent from here
 * until the user presses the send button (rendered with the other actions). */
export function Review({ review, onEdit, onCommand }: Props) {
  const text = useText();
  const sections = new Map<string, ReviewView["answered"]>();
  for (const row of review.answered) {
    sections.set(row.section, [...(sections.get(row.section) ?? []), row]);
  }
  return (
    <div className="review">
      {[...sections].map(([section, rows]) => (
        <section key={section} aria-labelledby={`section-${slug(section)}`}>
          <h2 id={`section-${slug(section)}`}>{section}</h2>
          <dl>
            {rows.map((row) => (
              <div className="review-row" key={row.field_id}>
                <dt id={`label-${row.field_id}`}>{capitalize(row.label)}</dt>
                <dd>{row.display}</dd>
                <dd>
                  <button
                    type="button"
                    className="secondary"
                    aria-describedby={`label-${row.field_id}`}
                    onClick={() => onEdit(row.field_id)}
                  >
                    {text.labels.change}
                  </button>
                </dd>
              </div>
            ))}
          </dl>
        </section>
      ))}
      {review.missing.length > 0 && (
        <section aria-labelledby="still-needed">
          <h2 id="still-needed">{text.labels.still_needed}</h2>
          <ul className="missing">
            {review.missing.map((item) => (
              <li key={item.field_id}>
                <p id={`missing-${item.field_id}`}>
                  <strong>{capitalize(item.label)}</strong>
                  {item.state !== text.labels.still_needed && <span>: {item.state}</span>}
                </p>
                {item.reason && <p className="reason">{item.reason}</p>}
                <div className="row-actions">
                  {item.actions.map((action) => (
                    <button
                      key={action.id}
                      type="button"
                      className="secondary"
                      aria-describedby={`missing-${item.field_id}`}
                      onClick={() =>
                        action.id === "mark_unknown"
                          ? onCommand({ kind: "mark_unknown", field_id: item.field_id })
                          : onEdit(item.field_id)
                      }
                    >
                      {action.label}
                    </button>
                  ))}
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

const slug = (text: string) => text.toLowerCase().replace(/[^a-z0-9]+/g, "-");
const capitalize = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);
