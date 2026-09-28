import { act, renderHook, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createRef } from "react";
import { question, renderWithText, turn } from "../test-utils";
import { useReading } from "../useReading";
import { orderedOptions } from "./Answer";
import { Bar } from "./Bar";
import { Review } from "./Review";
import { TurnScreen } from "./TurnScreen";

const noop = () => undefined;

function screenFor(view = turn(), onCommand = vi.fn()) {
  const ref = createRef<HTMLHeadingElement>();
  renderWithText(
    <TurnScreen view={view} headingRef={ref} onCommand={onCommand} onAction={noop} onEdit={noop} />,
  );
  return { ref, onCommand };
}

const choiceQuestion = question({
  field_id: "gender",
  input_type: "choice",
  text: "What is your gender?",
  options: [
    { id: "not_sure", label: "I'm not sure", free_text: false },
    { id: "woman", label: "Woman", free_text: false },
    { id: "other", label: "Another gender (type it)", free_text: true },
  ],
});

describe("one question per screen", () => {
  it("shows the question as the only page heading", () => {
    screenFor();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("What is your full name?");
  });

  it("puts 'I'm not sure' last, wherever the data puts it", () => {
    expect(orderedOptions(choiceQuestion).map((o) => o.id)).toEqual(["woman", "other", "not_sure"]);
    screenFor(turn({ question: choiceQuestion }));
    const buttons = screen.getAllByRole("button").filter((b) => b.closest(".options"));
    expect(buttons.at(-1)).toHaveTextContent("I'm not sure");
  });

  it("shows the example under a typed answer", () => {
    screenFor();
    expect(screen.getByLabelText("Your answer")).toHaveAccessibleDescription("Example: Alex Rivera");
  });

  it("keeps 'Why are you asking this?' right under the question, closed until asked", async () => {
    screenFor();
    const why = screen.getByRole("button", { name: "Why are you asking this?" });
    expect(why).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("We use this to find your records.")).toBeNull();
    await userEvent.click(why);
    expect(screen.getByText("We use this to find your records.")).toBeVisible();
  });
});

describe("never auto-advance", () => {
  it("typing sends nothing; only Send does", async () => {
    const { onCommand } = screenFor();
    await userEvent.type(screen.getByLabelText("Your answer"), "Alex Rivera");
    expect(onCommand).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(onCommand).toHaveBeenCalledWith({ kind: "text", text: "Alex Rivera" });
  });

  it("a free-text option opens its box on the same screen and sends only on Send", async () => {
    const { onCommand } = screenFor(turn({ question: choiceQuestion }));
    await userEvent.click(screen.getByRole("button", { name: "Another gender (type it)" }));
    expect(onCommand).not.toHaveBeenCalled();
    await userEvent.type(screen.getByLabelText("Another gender (type it)"), "Agender");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(onCommand).toHaveBeenCalledWith({ kind: "choose", option_id: "other", extra_text: "Agender" });
  });
});

describe("the fixed bar", () => {
  const renderBar = (view = turn()) =>
    renderWithText(
      <Bar view={view} code={null} onSkip={noop} onBreak={noop} onShowCode={noop} />,
    );

  it("shows 'Answer later' for needed questions and 'Skip' for optional ones", () => {
    renderBar();
    expect(screen.getByRole("button", { name: "Answer later" })).toBeInTheDocument();
  });

  it("keeps Take a break and Show my code in the same place", () => {
    renderBar(turn({ question: question({ can_skip: true, can_defer: false }) }));
    const buttons = screen.getAllByRole("button").map((b) => b.textContent);
    expect(buttons).toEqual(["Skip", "Take a break", "Show my code"]);
  });
});

describe("review", () => {
  it("groups answers by section and lists what is still needed", () => {
    renderWithText(
      <Review
        onEdit={noop}
        onCommand={noop}
        review={{
          can_submit: true,
          answered: [
            { field_id: "full_name", section: "About you", label: "full name", display: "Alex" },
            { field_id: "email", section: "Contact details", label: "email", display: "a@example.com" },
          ],
          missing: [
            {
              field_id: "date_of_birth",
              label: "date of birth",
              state: "Still needed",
              reason: null,
              actions: [{ id: "answer_now", label: "Answer now" }],
            },
          ],
        }}
      />,
    );
    const headings = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    expect(headings).toEqual(["About you", "Contact details", "Still needed"]);
    expect(screen.getByRole("button", { name: "Answer now" })).toHaveAccessibleDescription(
      "Date of birth",
    );
  });
});

describe("reading status", () => {
  it("appears only after 1 second of waiting", () => {
    vi.useFakeTimers();
    const { result, rerender } = renderHook(({ pending }) => useReading(pending), {
      initialProps: { pending: true },
    });
    act(() => void vi.advanceTimersByTime(900));
    expect(result.current).toBe(false);
    act(() => void vi.advanceTimersByTime(200));
    expect(result.current).toBe(true);
    rerender({ pending: false });
    expect(result.current).toBe(false);
    vi.useRealTimers();
  });
});
