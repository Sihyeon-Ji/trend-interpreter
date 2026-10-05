import { expect, test } from "@playwright/test";

/* 이 서비스는 어떻게 만들어지나요(Plan 14 0단계) — 이용자 말로 쓴 만드는 순서. 모델 건수·버전은 관리 화면에만 있다. */

test("how-it-is-made page is linked from the footer and explains the steps without model counts", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("contentinfo").getByRole("link", { name: /어떻게 만들어지나요|How this service is made/ }).click();
  await expect(page).toHaveURL(/\/about$/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(/어떻게 만들어지나요|How this service is made/);
  await expect(page.getByRole("listitem").filter({ hasText: /써도 되는지 판단|Judge whether to use it/ })).toBeVisible();
  await expect(page.getByRole("table")).toHaveCount(0);                       // 건수 표는 관리 화면에만
  await expect(page.getByRole("navigation").getByRole("link", { name: /Gemma/ })).toHaveCount(0);   // 주 메뉴에 모델 이름이 없다

  await page.goto("/about/gemma");                                           // 하루 공개됐던 옛 주소
  await expect(page).toHaveURL(/\/about$/);
});
