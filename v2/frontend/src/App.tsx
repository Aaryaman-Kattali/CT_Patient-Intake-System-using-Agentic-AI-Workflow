import { useCallback, useEffect, useRef, useState } from "react";
import {
  api,
  ApiFailure,
  type ActionView,
  type ReplyCommand,
  type ResumeCodeView,
  type Session,
  type TurnView,
  type UiText,
} from "./api/client";
import { AfterSubmit } from "./components/AfterSubmit";
import { Bar } from "./components/Bar";
import { EnterCode } from "./components/EnterCode";
import { TextSize } from "./components/TextSize";
import { headingOf, Progress, TurnScreen } from "./components/TurnScreen";
import { emailKey, loadSession, saveSession } from "./storage";
import { OFFLINE, TextContext } from "./text";
import { useReading } from "./useReading";

const WITH_BAR = new Set(["choose_intake_type", "collecting", "confirming_extra", "resolving_conflict", "review"]);

interface CodeEntry {
  message: string | null;
  actions: ActionView[];
  help: string[];
}

const NO_CODE_ENTRY: CodeEntry = { message: null, actions: [], help: [] };

export function App() {
  const [ui, setUi] = useState<UiText | null>(null);
  const [offline, setOffline] = useState(false);
  const [session, setSession] = useState<Session | null>(null);
  const [view, setView] = useState<TurnView | null>(null);
  const [mode, setMode] = useState<"turn" | "code">("turn");
  const [pending, setPending] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [code, setCode] = useState<ResumeCodeView | null>(null);
  const [codeEntry, setCodeEntry] = useState<CodeEntry>(NO_CODE_ENTRY);
  const [announcement, setAnnouncement] = useState("");
  const headingRef = useRef<HTMLHeadingElement>(null);
  const busy = useRef(false);
  const reading = useReading(pending);

  const failed = useCallback(
    (error: unknown) => {
      const body = error instanceof ApiFailure ? error.body : null;
      if (body?.code === "intake_not_found") saveSession(null);
      if (body?.view) setView(body.view);
      const message = body ? body.message : (ui?.sentences.no_connection ?? OFFLINE);
      setNotice(body?.view?.info.includes(message) ? null : message);
    },
    [ui],
  );

  /** One user action -> one request. Nothing on screen changes without an action. */
  const act = useCallback(
    async (request: () => Promise<void>) => {
      if (busy.current) return; // a double click sends nothing twice
      busy.current = true;
      setPending(true);
      setNotice(null);
      try {
        await request();
      } catch (error) {
        failed(error);
      } finally {
        busy.current = false;
        setPending(false);
      }
    },
    [failed],
  );

  const open = useCallback((s: Session, next: TurnView) => {
    saveSession(s);
    setSession(s);
    setView(next);
    setCode(null);
  }, []);

  const newForm = useCallback(async () => {
    const created = await api.create();
    open({ id: created.id, token: created.token }, created.view);
  }, [open]);

  // First load: the wording, then this device's form (or a new one).
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const text = await api.uiText();
        if (cancelled) return;
        setUi(text);
        const stored = loadSession();
        if (stored) {
          try {
            open(stored, await api.get(stored));
            return;
          } catch {
            saveSession(null); // gone or not ours: start fresh
          }
        }
        await newForm();
      } catch {
        if (!cancelled) setOffline(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open, newForm]);

  // A new turn: move focus to the heading, so the new question is read out.
  useEffect(() => {
    headingRef.current?.focus();
  }, [mode, view?.turn, view?.state]);

  // Every new response is announced politely: acknowledgement, heading, then any text.
  useEffect(() => {
    if (!view || !ui || mode !== "turn") return;
    const { heading, rest } = headingOf(view, ui.labels.review_title ?? "");
    setAnnouncement([view.acknowledgement, heading, ...rest].filter(Boolean).join(" "));
  }, [view, ui, mode]);

  if (offline) return <p className="notice">{OFFLINE}</p>;
  if (!ui || !view || !session) return <div className="app" aria-busy="true" />;

  const turn = view.turn;
  const setTurn = async (next: Promise<TurnView>) => {
    setView(await next);
    setCode(null);
  };
  const command = (c: ReplyCommand) => act(() => setTurn(api.reply(session, turn, c)));
  const onAction = (id: string) => {
    const run: Record<string, () => Promise<void>> = {
      start: () => setTurn(api.start(session, turn)),
      resume: () => setTurn(api.resume(session, turn)),
      continue_alone: () => setTurn(api.resume(session, turn)),
      submit: () => setTurn(api.submit(session, turn)),
      take_a_break: () => setTurn(api.pause(session, turn)),
      keep_going: () => setTurn(api.reply(session, turn, { kind: "keep_going" })),
      talk_to_a_person: () => setTurn(api.reply(session, turn, { kind: "talk_to_person" })),
      undo: () => setTurn(api.reply(session, turn, { kind: "undo" })),
      answer_later: () => setTurn(api.reply(session, turn, { kind: "skip" })),
    };
    const request = run[id];
    if (request) void act(request);
  };

  const content =
    mode === "code" ? (
      <EnterCode
        headingRef={headingRef}
        {...codeEntry}
        onSend={(typed) =>
          void act(async () => {
            try {
              const opened = await api.resumeWithCode(typed);
              open({ id: opened.id, token: opened.token }, opened.view);
              setCodeEntry(NO_CODE_ENTRY);
              setMode("turn");
            } catch (error) {
              const body = error instanceof ApiFailure ? error.body : null;
              if (!body) throw error;
              setCodeEntry({ message: body.message, actions: body.actions, help: [] });
            }
          })
        }
        onAction={() =>
          void act(async () => {
            const help = await api.help();
            setCodeEntry((entry) => ({ ...entry, help: help.info }));
          })
        }
        onBack={() => {
          setCodeEntry(NO_CODE_ENTRY);
          setMode("turn");
        }}
      />
    ) : (
      <>
        <TurnScreen
          view={view}
          headingRef={headingRef}
          onCommand={(c) => void command(c)}
          onAction={onAction}
          onEdit={(fieldId) => void act(() => setTurn(api.edit(session, turn, fieldId)))}
        />
        {view.state === "greeting" && (
          <div className="actions">
            <button type="button" className="secondary" onClick={() => setMode("code")}>
              {ui.labels.have_code}
            </button>
          </div>
        )}
        {view.state === "submitted" && (
          <AfterSubmit
            onEmail={() => void act(() => setTurn(api.email(session, emailKey(session.id))))}
            onNewForm={() => void act(newForm)}
          />
        )}
      </>
    );

  return (
    <TextContext.Provider value={ui}>
      <div className="app">
        <header className="top">
          <TextSize />
        </header>
        <main>
          {mode === "turn" && WITH_BAR.has(view.state) && <Progress view={view} />}
          {content}
          {notice && <p className="notice">{notice}</p>}
          <p role="status" className="reading">
            {reading ? ui.sentences.reading : ""}
          </p>
          {mode === "turn" && WITH_BAR.has(view.state) && (
            <Bar
              view={view}
              code={code}
              onSkip={() => void command({ kind: "skip" })}
              onBreak={() => onAction("take_a_break")}
              onShowCode={() => void act(async () => setCode(await api.resumeCode(session)))}
            />
          )}
        </main>
        <div className="visually-hidden" aria-live="polite">
          {announcement}
        </div>
      </div>
    </TextContext.Provider>
  );
}
