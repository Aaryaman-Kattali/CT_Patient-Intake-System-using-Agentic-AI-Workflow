// Browser storage for per-device conveniences only: the session token (so closing the tab
// and coming back resumes on this device), the email request key, and the text size.
// Storage can be missing or blocked; every access is guarded and the app works without it.
import type { Session } from "./api/client";

const SESSION = "intake.session";

function read(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string | null): void {
  try {
    if (value === null) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, value);
  } catch {
    // Storage is blocked: the app still works, it just cannot resume after the tab closes.
  }
}

export function loadSession(): Session | null {
  try {
    const parsed: unknown = JSON.parse(read(SESSION) ?? "null");
    if (parsed && typeof parsed === "object" && "id" in parsed && "token" in parsed) {
      const { id, token } = parsed as Session;
      if (typeof id === "string" && typeof token === "string") return { id, token };
    }
  } catch {
    // ignore a damaged value
  }
  return null;
}

export const saveSession = (s: Session | null) => write(SESSION, s ? JSON.stringify(s) : null);

/** One key per intake, so a repeated click or a retry never sends a second email. */
export function emailKey(intakeId: string): string {
  const key = `intake.emailKey.${intakeId}`;
  const existing = read(key);
  if (existing) return existing;
  const created = crypto.randomUUID();
  write(key, created);
  return created;
}

export const loadTextScale = () => Number(read("intake.textScale")) || 1;
export const saveTextScale = (scale: number) => write("intake.textScale", String(scale));
