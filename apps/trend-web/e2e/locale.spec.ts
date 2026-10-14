import { expect, test } from "@playwright/test";

/* 첫 방문의 언어(10-14): 고른 언어(쿠키)가 없으면 브라우저 언어, 주소의 ?lang= 은 쿠키로 저장하고 떼어 낸다 */
test.describe("an English browser", () => {
  test.use({ locale: "en-US" });
  test("opens in English without choosing", async ({ page }) => {
    await page.goto("/about");
    await expect(page.locator("html")).toHaveAttribute("lang", /^en/);
  });
});

test("?lang= sets the language and is removed from the address", async ({ page }) => {
  await page.goto("/about?lang=ja");
  await expect(page).toHaveURL(/\/about$/);
  await expect(page.locator("html")).toHaveAttribute("lang", /^ja/);
  await page.goto("/dictionary");
  await expect(page.locator("html")).toHaveAttribute("lang", /^ja/);
});
