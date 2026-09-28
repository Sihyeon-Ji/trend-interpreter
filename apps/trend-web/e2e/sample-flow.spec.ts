import { expect, test } from "@playwright/test";

test("sample trend board and dictionary open without a model", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveTitle(/Trend Interpreter/);
  await expect(page.getByRole("main")).toBeVisible();

  await page.goto("/dictionary");
  await expect(page).toHaveURL(/\/dictionary$/);
  await expect(page.getByRole("main")).toBeVisible();
});
