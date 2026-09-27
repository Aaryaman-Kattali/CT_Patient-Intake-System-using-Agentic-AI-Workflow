import { expect, test, type Page } from "@playwright/test";
import { answer, checkScreen, choose, expectQuestion, heading, openNewForm } from "./helpers";

/** Skip the optional questions until the review screen. */
async function skipToReview(page: Page): Promise<void> {
  for (let i = 0; i < 8 && (await heading(page).textContent()) !== "Check your answers"; i++) {
    await choose(page, "Skip");
    await expect(heading(page)).toBeFocused();
  }
  await expect(heading(page)).toHaveText("Check your answers");
}

async function toFullName(page: Page): Promise<void> {
  await openNewForm(page);
  await choose(page, "Start");
  await choose(page, "Care for me or someone I look after");
  await choose(page, "Me");
  await expectQuestion(page, "What is your full name?");
}

test("the reading status appears only after 1 second of waiting", async ({ page }) => {
  await toFullName(page);
  const status = page.locator(".reading");
  await page.getByLabel("Your answer").fill("slow: Alex Rivera");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await page.waitForTimeout(500);
  await expect(status).toHaveText("");
  await expect(status).toHaveText("Reading your answer…", { timeout: 1500 });
  await expectQuestion(page, "What is your date of birth?");
  await expect(status).toHaveText("");
});

test("nothing changes until the user acts", async ({ page }) => {
  await toFullName(page);
  let replies = 0;
  page.on("request", (r) => {
    if (r.url().endsWith("/replies")) replies += 1;
  });
  await page.getByLabel("Your answer").pressSequentially("Alex Rive");
  await page.waitForTimeout(2500);
  expect(replies).toBe(0);
  await expect(heading(page)).toHaveText("What is your full name?");
});

test("closing the tab and coming back resumes on this device", async ({ page }) => {
  await toFullName(page);
  await answer(page, "Alex Rivera");
  await expectQuestion(page, "What is your date of birth?");
  await page.reload();
  await expect(heading(page)).toHaveText("What is your date of birth?");
});

test("a code opens the form on another device", async ({ page, browser }) => {
  await toFullName(page);
  await choose(page, "Take a break");
  const code = (await page.locator(".code").textContent()) ?? "";
  const other = await (await browser.newContext()).newPage();
  await openNewForm(other);
  await choose(other, "I have a code");
  await other.getByLabel("Your code").fill(code.toLowerCase().replace("-", " "));
  await choose(other, "Go back to my form");
  await expect(heading(other)).toHaveText("What is your full name?");
});

test("too many wrong codes: one calm message and a way to a person", async ({ page }) => {
  await openNewForm(page);
  await choose(page, "I have a code");
  const wrong = `WXY-Z${"23456789"[Date.now() % 8]}${"ABCDEFGH"[Date.now() % 7]}`;
  const attempt = async () => {
    await page.getByLabel("Your code").fill(wrong);
    await Promise.all([
      page.waitForResponse((r) => r.url().endsWith("/intakes/resume")),
      choose(page, "Go back to my form"),
    ]);
  };
  for (let i = 0; i < 5; i++) {
    await attempt();
    await expect(page.locator(".notice")).toHaveText(
      "That code did not work. Please check it and try again.",
    );
  }
  await attempt();
  await expect(page.locator(".notice")).toHaveText(
    "Please wait 15 minutes, then try again. Your answers are safe.",
  );
  await choose(page, "Talk to a person");
  await expect(
    page.getByText("This is a demo. No one will contact you.", { exact: true }),
  ).toBeVisible();
});

test("text size can be changed and is remembered", async ({ page }) => {
  await openNewForm(page);
  await choose(page, "Bigger text");
  const size = () => page.evaluate(() => document.documentElement.style.fontSize);
  expect(await size()).toBe("115%");
  await page.reload();
  await expect(heading(page)).toBeVisible();
  expect(await size()).toBe("115%");
});

test("changing the kind of form from review goes back to review", async ({ page }) => {
  await toFullName(page);
  await answer(page, "Alex Rivera");
  await expectQuestion(page, "What is your date of birth?");
  await answer(page, "May 4, 2004");
  await choose(page, "Phone call");
  await answer(page, "202-555-0100");
  await choose(page, "Therapy or support");
  await skipToReview(page);
  await page.locator("[aria-describedby='label-intake_type']").click();
  await expectQuestion(page, "Which one describes you?");
  await choose(page, "Care for me or someone I look after");
  await expect(heading(page)).toHaveText("Check your answers");
});

test("after sending: email once, and the staff drafts", async ({ page }) => {
  await toFullName(page);
  await answer(page, "Alex Rivera");
  await expectQuestion(page, "What is your date of birth?");
  await answer(page, "May 4, 2004");
  await choose(page, "Email");
  await answer(page, "alex@example.com");
  await choose(page, "Therapy or support");
  await skipToReview(page);
  await choose(page, "Send my form");
  await choose(page, "Email me a confirmation");
  const sent = page.getByText("We sent an email to say we have your form.", { exact: true });
  await expect(sent).toBeVisible();
  await choose(page, "Email me a confirmation"); // same request key: nothing new is sent
  await expect(page.locator(".notice")).toHaveCount(0);
  await expect(page.getByText(/staff summary|benefit/i)).toHaveCount(0); // not on the patient's page

  // The staff view is a separate page, opened by its address only.
  const id = await page.evaluate(
    () => (JSON.parse(localStorage.getItem("intake.session") ?? "{}") as { id?: string }).id,
  );
  await page.goto(`/staff/${id}`);
  await expect(heading(page)).toHaveText("Staff view (demo)");
  await expect(page.getByText("Full name: Alex Rivera")).toBeVisible();
  await expect(page.locator(".synthetic-band")).toHaveCount(2); // top and bottom
  await checkScreen(page, "15-staff-view");
});

test("the staff view opens only where the form was filled in", async ({ page }) => {
  await page.goto("/staff/00000000-0000-4000-8000-000000000000");
  await expect(heading(page)).toHaveText("Staff view (demo)");
  await expect(page.locator(".notice")).toHaveText(
    "Open this page in the browser where the form was filled in.",
  );
});

test("autofill hints only for the person typing", async ({ page, browser }) => {
  await toFullName(page); // "Me": the patient is the person typing
  await expect(page.getByLabel("Your answer")).toHaveAttribute("autocomplete", "name");

  const other = await (await browser.newContext()).newPage();
  await openNewForm(other);
  await choose(other, "Start");
  await choose(other, "Care for me or someone I look after");
  await choose(other, "My child");
  await expect(other.getByLabel("Your answer")).toHaveAttribute("autocomplete", "name"); // their name
  await answer(other, "Jordan Rivera");
  await expect(heading(other)).toHaveText("What is the patient's full name?");
  await expect(other.getByLabel("Your answer")).toHaveAttribute("autocomplete", "off");
});
