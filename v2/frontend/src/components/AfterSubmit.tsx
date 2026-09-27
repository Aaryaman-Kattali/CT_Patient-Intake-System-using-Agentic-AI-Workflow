import type { BenefitSummary, StaffSummary } from "../api/client";
import { useText } from "../text";

interface Props {
  onEmail: () => void;
  onStaffSummary: () => void;
  onBenefit: () => void;
  onNewForm: () => void;
  staff: StaffSummary | null;
  benefit: BenefitSummary | null;
}

/** After sending: an optional confirmation email, and the staff drafts (clearly a demo). */
export function AfterSubmit({ onEmail, onStaffSummary, onBenefit, onNewForm, staff, benefit }: Props) {
  const text = useText();
  return (
    <>
      <div className="actions">
        <button type="button" onClick={onEmail}>
          {text.labels.email_me}
        </button>
        <button type="button" className="secondary" onClick={onNewForm}>
          {text.labels.new_form}
        </button>
      </div>
      <section className="staff" aria-labelledby="staff-title">
        <h2 id="staff-title">{text.labels.staff_title}</h2>
        <div className="actions">
          <button type="button" className="secondary" onClick={onStaffSummary}>
            {text.labels.staff_summary}
          </button>
          <button type="button" className="secondary" onClick={onBenefit}>
            {text.labels.benefit_summary}
          </button>
        </div>
        {staff && <StaffView summary={staff} />}
        {benefit && <BenefitView demo={benefit} />}
      </section>
    </>
  );
}

function StaffView({ summary }: { summary: StaffSummary }) {
  const parts: [string, StaffSummary["notes"]][] = [
    ...Object.entries(summary.sections),
    ["", summary.not_answered],
    ["", summary.notes],
  ];
  return (
    <article className="draft">
      <h3>{summary.title}</h3>
      <p>{summary.disclaimer}</p>
      {parts
        .filter(([, statements]) => statements.length > 0)
        .map(([name, statements], i) => (
          <div key={`${name}-${i}`}>
            {name && <h4>{name}</h4>}
            <ul>
              {statements.map((s) => (
                <li key={s.text}>
                  {s.text} <span className="sources">({s.sources.join(", ")})</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
    </article>
  );
}

function BenefitView({ demo }: { demo: BenefitSummary }) {
  return (
    <article className="draft">
      <p className="demo-label">{demo.label_top}</p>
      <h3>{demo.title}</h3>
      <p>{demo.member_name}</p>
      <dl>
        {demo.lines.map((line) => (
          <div className="review-row" key={line.label}>
            <dt>{line.label}</dt>
            <dd>{line.value}</dd>
          </div>
        ))}
      </dl>
      <p className="demo-label">{demo.label_bottom}</p>
    </article>
  );
}
