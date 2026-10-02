import { test, expect } from "@playwright/test";

test("report search keeps its browser filter separate from the server index loader", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/lab/f-report");
  const response = page.waitForResponse((res) => res.url().includes("/lab/f-report/api/search") && res.request().method() === "GET");
  const search = page.getByRole("combobox");
  await search.fill("推し活");
  expect((await response).ok()).toBe(true);
  const option = page.getByRole("option").filter({ hasText: "推し活" });
  await expect(option).toBeVisible();
  await option.click();
  await expect(page).toHaveURL(/\/lab\/f-report\/m\/t_oshikatsu/);
  expect(errors).toEqual([]);
});
