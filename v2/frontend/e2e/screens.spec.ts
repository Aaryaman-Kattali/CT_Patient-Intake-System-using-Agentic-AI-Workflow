import { expect, test } from "@playwright/test";
import { answer, checkScreen, choose, expectQuestion, heading, openNewForm } from "./helpers";

test.use({ viewport: { width: 900, height: 1000 } });

test("every screen type: accessible, one question, fixed layout", async ({ page }) => {
  await openNewForm(page);
  await checkScreen(page, "01-start");

  await choose(page, "Start");
  await expectQuestion(page, "Which one describes you?");
  const options = page.locator(".options button");
  await expect(options.last()).toHaveText("I'm not sure");
  await checkScreen(page, "02-choice-question");

  await choose(page, "Care for me or someone I look after");
  await expectQuestion(page, "Who is this form for?");
  await choose(page, "Me");
  await expectQuestion(page, "What is your full name?");
  await expect(page.getByText("Example: Alex Rivera")).toBeVisible();
  await checkScreen(page, "03-text-question");

  // A reply with an ambiguous date: two date buttons.
  await answer(page, "Alex Rivera; date_of_birth=04/05/2004");
  await expectQuestion(page, "Which date do you mean?");
  await checkScreen(page, "04-date-choice");
  await choose(page, "May 4, 2004");

  await expectQuestion(page, "How do you want us to contact you?");
  await choose(page, "Email");
  await expectQuestion(page, "What is your email address?");
  // An extra value in a reply: confirmed with yes/no, never saved silently.
  await answer(page, "alex@example.com; preferred_name=Alex");
  await expectQuestion(page, "Name to use: Alex. Is that right?");
  await checkScreen(page, "05-confirmation");
  await choose(page, "Yes");

  await expectQuestion(page, "What do you want help with?");
  await choose(page, "An autism assessment");
  await expectQuestion(page, "What is your phone number?");
  // A different value for an answered field: the conflict question.
  await answer(page, "202-555-0100; full_name=Sam Park");
  await expect(heading(page)).toContainText("Which one is correct?");
  await checkScreen(page, "06-conflict");
  await choose(page, "Alex Rivera");

  await expectQuestion(page, "What is your home address?");
  await choose(page, "Skip");
  await expectQuestion(page, "What is your gender?");
  await choose(page, "Prefer not to say");

  await expect(heading(page)).toHaveText("Check your answers");
  await checkScreen(page, "07-review");

  await choose(page, "Show my code");
  await expect(page.locator(".code")).toHaveText(/^[A-Z2-9]{3}-[A-Z2-9]{3}$/);
  await checkScreen(page, "08-show-my-code");

  await choose(page, "Take a break");
  await expect(heading(page)).toHaveText("Your answers are saved.");
  await checkScreen(page, "09-take-a-break");
  await choose(page, "Go back to my form");
  await expect(heading(page)).toHaveText("Check your answers");

  // Distress: fixed text and three calm choices.
  await page
    .getByRole("button", { name: "Change" })
    .and(page.locator("[aria-describedby='label-full_name']"))
    .click();
  await expectQuestion(page, "What is your full name?");
  await answer(page, "too much for me right now");
  await expect(heading(page)).toHaveText("This can feel like a lot. That is okay.");
  await checkScreen(page, "10-distress");
  await choose(page, "Keep going");
  await expectQuestion(page, "What is your full name?");
  await answer(page, "Alex Rivera");

  await expect(heading(page)).toHaveText("Check your answers");
  await choose(page, "Send my form");
  await expect(heading(page)).toHaveText("Thank you. We have your form.");
  await checkScreen(page, "11-submitted");
});

test("crisis words get the fixed crisis response", async ({ page }) => {
  await openNewForm(page);
  await choose(page, "Start");
  await choose(page, "Care for me or someone I look after");
  await choose(page, "Me");
  await answer(page, "I want to kill myself");
  await expect(heading(page)).toHaveText("You can get help now.");
  await expect(
    page.getByText("This is a demo. No one will contact you.", { exact: true }),
  ).toBeVisible();
  await checkScreen(page, "12-crisis");
});

test("resume code entry screen", async ({ page }) => {
  await openNewForm(page);
  await choose(page, "I have a code");
  await expect(heading(page)).toHaveText("Type your code");
  await checkScreen(page, "13-enter-code");
});

test("phone width: no sideways scrolling", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await openNewForm(page);
  await choose(page, "Start");
  await expectQuestion(page, "Which one describes you?");
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(overflow).toBe(false);
  await checkScreen(page, "14-phone-choice-question");
});
