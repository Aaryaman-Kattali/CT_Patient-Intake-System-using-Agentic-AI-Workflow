import { render, type RenderResult } from "@testing-library/react";
import type { ReactElement } from "react";
import type { QuestionView, TurnView, UiText } from "./api/client";
import { TextContext } from "./text";

// Test wording. The real wording comes from the backend (GET /ui/text).
export const UI: UiText = {
  buttons: {
    why: "Why are you asking this?",
    skip: "Skip",
    answer_later: "Answer later",
    take_a_break: "Take a break",
    start: "Start",
    submit: "Send my form",
  },
  labels: {
    send: "Send",
    answer_box: "Your answer",
    review_title: "Check your answers",
    change: "Change",
    still_needed: "Still needed",
    show_code: "Show my code",
    your_code: "Your code",
    copy_code: "Copy code",
    progress: "Your progress",
    done: "Done",
    text_size: "Text size",
    text_bigger: "Bigger text",
    text_smaller: "Smaller text",
  },
  sentences: {
    reading: "Reading your answer…",
    example: "Example: {example}",
    progress: "Question {number} of about {total}",
    code_copied: "The code is copied.",
  },
};

export function renderWithText(ui: ReactElement): RenderResult {
  return render(<TextContext.Provider value={UI}>{ui}</TextContext.Provider>);
}

export function question(overrides: Partial<QuestionView> = {}): QuestionView {
  return {
    kind: "field",
    field_id: "full_name",
    text: "What is your full name?",
    example: "Alex Rivera",
    input_type: "text",
    options: [],
    why: "We use this to find your records.",
    can_skip: false,
    can_defer: true,
    ...overrides,
  };
}

export function turn(overrides: Partial<TurnView> = {}): TurnView {
  return {
    state: "collecting",
    turn: 3,
    acknowledgement: null,
    info: [],
    question: question(),
    actions: [{ id: "take_a_break", label: "Take a break" }],
    progress: { answered: 3, about_total: 12, exact: true, sections: [] },
    review: null,
    resume_code: null,
    ...overrides,
  };
}
