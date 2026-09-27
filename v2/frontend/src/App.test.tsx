import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { api } from "./api/client";
import { App } from "./App";
import { question, turn, UI } from "./test-utils";

vi.mock("./api/client", async (original) => {
  const real = await original<typeof import("./api/client")>();
  return {
    ...real,
    api: { uiText: vi.fn(), get: vi.fn(), create: vi.fn(), reply: vi.fn(), start: vi.fn() },
  };
});

const mocked = vi.mocked(api);
const SESSION = { id: "00000000-0000-4000-8000-000000000001", token: "t" };

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
  mocked.uiText.mockResolvedValue(UI);
});

it("resumes the form stored on this device, without a new one", async () => {
  window.localStorage.setItem("intake.session", JSON.stringify(SESSION));
  mocked.get.mockResolvedValue(turn());
  render(<App />);
  expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent(
    "What is your full name?",
  );
  expect(mocked.get).toHaveBeenCalledWith(SESSION);
  expect(mocked.create).not.toHaveBeenCalled();
});

it("starts a new form when none is stored", async () => {
  mocked.create.mockResolvedValue({ ...SESSION, view: turn() });
  render(<App />);
  await screen.findByRole("heading", { level: 1 });
  expect(mocked.create).toHaveBeenCalledOnce();
  expect(JSON.parse(window.localStorage.getItem("intake.session") ?? "null")).toEqual(SESSION);
});

it("moves focus to the new question and announces it politely", async () => {
  window.localStorage.setItem("intake.session", JSON.stringify(SESSION));
  mocked.get.mockResolvedValue(turn());
  const next = turn({
    turn: 4,
    acknowledgement: "Saved.",
    question: question({ field_id: "date_of_birth", text: "What is your date of birth?" }),
  });
  mocked.reply.mockResolvedValue(next);
  render(<App />);
  await userEvent.type(await screen.findByLabelText("Your answer"), "Alex Rivera");
  await userEvent.click(screen.getByRole("button", { name: "Send" }));
  const heading = await screen.findByRole("heading", { name: "What is your date of birth?" });
  await waitFor(() => expect(heading).toHaveFocus());
  const live = document.querySelector("[aria-live='polite'].visually-hidden");
  expect(live).toHaveTextContent("Saved. What is your date of birth?");
  expect(mocked.reply).toHaveBeenCalledWith(SESSION, 3, { kind: "text", text: "Alex Rivera" });
});

it("a refused answer keeps focus in the box and says why", async () => {
  window.localStorage.setItem("intake.session", JSON.stringify(SESSION));
  mocked.get.mockResolvedValue(turn());
  mocked.reply.mockResolvedValue(turn({ info: ["That message is too long for me to read."] }));
  render(<App />);
  const box = await screen.findByLabelText("Your answer");
  await userEvent.type(box, "x");
  await userEvent.click(screen.getByRole("button", { name: "Send" }));
  expect(await screen.findByText("That message is too long for me to read.")).toBeVisible();
  const live = document.querySelector("[aria-live='polite'].visually-hidden");
  expect(live).toHaveTextContent("That message is too long for me to read.");
  expect(screen.getByRole("heading", { level: 1 })).not.toHaveFocus(); // same turn: no jump
});
