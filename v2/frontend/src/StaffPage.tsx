// Staff view (demo): /staff/<intake id>. Reached only by typing the address (see README).
// The patient pages never link here. This demo has no staff login: it uses the intake token
// kept in this browser, so it only opens in the browser where the form was filled in.
import { useEffect, useState } from "react";
import {
  api,
  ApiFailure,
  type BenefitSummary,
  type StaffSummary,
  type UiText,
} from "./api/client";
import { loadSession } from "./storage";
import { OFFLINE, TextContext } from "./text";

type Loaded =
  | { kind: "loading" }
  | { kind: "message"; text: string }
  | { kind: "ready"; staff: StaffSummary; benefit: BenefitSummary };

export function StaffPage({ intakeId }: { intakeId: string }) {
  const [ui, setUi] = useState<UiText | null>(null);
  const [loaded, setLoaded] = useState<Loaded>({ kind: "loading" });

  useEffect(() => {
    void (async () => {
      let text: UiText;
      try {
        text = await api.uiText();
      } catch {
        setLoaded({ kind: "message", text: OFFLINE });
        return;
      }
      setUi(text);
      const session = loadSession();
      if (!session || session.id !== intakeId) {
        setLoaded({ kind: "message", text: text.sentences.staff_open_here ?? "" });
        return;
      }
      try {
        const [staff, benefit] = await Promise.all([
          api.staffSummary(session),
          api.benefitSummary(session),
        ]);
        setLoaded({ kind: "ready", staff, benefit });
      } catch (error) {
        const body = error instanceof ApiFailure ? error.body : null;
        setLoaded({ kind: "message", text: body?.message ?? OFFLINE });
      }
    })();
  }, [intakeId]);

  return (
    <TextContext.Provider value={ui}>
      <div className="staff-page">
        <header className="staff-band">
          <h1>{ui?.labels.staff_view}</h1>
        </header>
        <main className="staff-main">
          {loaded.kind === "message" && <p className="notice">{loaded.text}</p>}
          {loaded.kind === "ready" && (
            <>
              <StaffView summary={loaded.staff} />
              <BenefitView demo={loaded.benefit} />
            </>
          )}
        </main>
      </div>
    </TextContext.Provider>
  );
}

function StaffView({ summary }: { summary: StaffSummary }) {
  const parts: [string, StaffSummary["notes"]][] = [
    ...Object.entries(summary.sections),
    ["", summary.not_answered],
    ["", summary.notes],
  ];
  return (
    <article className="record" aria-labelledby="staff-summary-title">
      <h2 id="staff-summary-title">{summary.title}</h2>
      <p className="record-note">{summary.disclaimer}</p>
      {parts
        .filter(([, statements]) => statements.length > 0)
        .map(([name, statements], i) => (
          <section key={`${name}-${i}`}>
            {name && <h3>{name}</h3>}
            <ul className="statements">
              {statements.map((s) => (
                <li key={s.text}>
                  <span>{s.text}</span>
                  <span className="sources">{s.sources.join(", ")}</span>
                </li>
              ))}
            </ul>
          </section>
        ))}
    </article>
  );
}

function BenefitView({ demo }: { demo: BenefitSummary }) {
  return (
    <article className="record" aria-labelledby="benefit-title">
      <p className="synthetic-band">{demo.label_top}</p>
      <h2 id="benefit-title">{demo.title}</h2>
      <p>{demo.member_name}</p>
      <dl className="benefit-lines">
        {demo.lines.map((line) => (
          <div key={line.label}>
            <dt>{line.label}</dt>
            <dd>{line.value}</dd>
          </div>
        ))}
      </dl>
      <p className="synthetic-band">{demo.label_bottom}</p>
    </article>
  );
}
