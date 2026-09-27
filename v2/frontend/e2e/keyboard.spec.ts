import { expect, test, type Locator, type Page } from "@playwright/test";
import { heading, openNewForm } from "./helpers";

/** Keyboard only: Tab until the target has focus (no mouse, no clicks). */
async function tabTo(page: Page, target: Locator): Promise<void> {
  for (let i = 0; i < 40; i++) {
    await page.keyboard.press("Tab");
    if (await target.evaluate((el) => el === document.activeElement)) return;
  }
  throw new Error(`Tab never reached ${target.toString()}`);
}

async function press(page: Page, name: string): Promise<void> {
  await tabTo(page, page.getByRole("button", { name, exact: true }));
  await page.keyboard.press("Enter");
}

async function type(page: Page, text: string): Promise<void> {
  await tabTo(page, page.getByLabel("Your answer"));
  await page.keyboard.type(text);
  await page.keyboard.press("Enter");
}

/** After every answer, focus is on the new question heading. */
async function next(page: Page, question: string): Promise<void> {
  await expect(heading(page)).toHaveText(question);
  await expect(heading(page)).toBeFocused();
}

test("a full Family Inquiry with the keyboard only", async ({ page }) => {
  await openNewForm(page);
  await press(page, "Start");
  await next(page, "Which one describes you?");
  await press(page, "Care for me or someone I look after");
  await next(page, "Who is this form for?");
  await press(page, "Me");
  await next(page, "What is your full name?");
  await type(page, "Alex Rivera");
  await next(page, "What is your date of birth?");
  await type(page, "May 4, 2004");
  await next(page, "How do you want us to contact you?");
  await press(page, "Email");
  await next(page, "What is your email address?");
  await type(page, "alex@example.com");
  await next(page, "What do you want help with?");
  await press(page, "An autism assessment");
  await next(page, "What is your phone number?");
  await type(page, "202-555-0100");
  await next(page, "What is your home address?");
  await type(page, "12 Oak Street, Springfield, IL 62701");
  await next(page, "What name do you want us to use for you?");
  await press(page, "Skip");
  await next(page, "What is your gender?");
  await press(page, "Non-binary");
  await next(page, "Check your answers");
  await press(page, "Send my form");
  await next(page, "Thank you. We have your form.");
});
