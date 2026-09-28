// All wording comes from the backend (GET /ui/text), never from this code (principle P3).
import { createContext, useContext } from "react";
import type { UiText } from "./api/client";

export const TextContext = createContext<UiText | null>(null);

export function useText(): UiText {
  const text = useContext(TextContext);
  if (!text) throw new Error("UI text not loaded");
  return text;
}

/** Fill {placeholders} in a fixed sentence. */
export function fill(template: string, values: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (_, key: string) => String(values[key] ?? ""));
}

// Shown only if the API cannot be reached before its wording loads. Same words as the
// backend's `no_connection` sentence.
export const OFFLINE = "The form cannot be reached right now. Please try again in a moment.";
