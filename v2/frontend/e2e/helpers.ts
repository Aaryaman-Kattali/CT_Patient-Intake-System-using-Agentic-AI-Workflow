import AxeBuilder from "@axe-core/playwright";
import { expect, type Page } from "@playwright/test";

export const heading = (page: Page) => page.getByRole("heading", { level: 1 });
export const liveRegion = (page: Page) => page.locator(".visually-hidden[aria-live='polite']");

/** A fresh browser context has no stored session, so this starts a new form. */
export async function openNewForm(page: Page): Promise<void> {
  await page.goto("/");
  await expect(heading(page)).toHaveText("This form has about 12 questions.");
}

export async function choose(page: Page, label: string): Promise<void> {
  await page.getByRole("button", { name: label, exact: true }).click();
}

export async function answer(page: Page, text: string): Promise<void> {
  await page.getByLabel("Your answer").fill(text);
  await page.getByRole("button", { name: "Send", exact: true }).click();
}

/** The new question is the page heading, has focus, and is announced politely. */
export async function expectQuestion(page: Page, text: string): Promise<void> {
  await expect(heading(page)).toHaveText(text);
  await expect(heading(page)).toBeFocused();
  await expect(liveRegion(page)).toContainText(text);
}

/** axe (WCAG 2.2 A/AA) finds nothing, and a full-page screenshot is saved for review. */
export async function checkScreen(page: Page, name: string): Promise<void> {
  if (!page.url().includes("/staff/")) {
    // The patient's pages never lead to the staff view.
    await expect(page.locator("a[href*='/staff']")).toHaveCount(0);
    await expect(page.getByText("Staff view", { exact: false })).toHaveCount(0);
  }
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.help}`), name).toEqual([]);
  expect(await page.evaluate(() => document.getAnimations().length), "no motion").toBe(0);
  await page.screenshot({ path: `screenshots/${name}.png`, fullPage: true });
}
