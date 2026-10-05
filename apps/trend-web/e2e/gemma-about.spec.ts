import { expect, test } from "@playwright/test";

/* Gemma가 하는 일(Plan 14 0단계). 예시 모드는 건수를 지어내지 않고 설명·규칙만 보인다 — 실제 건수는 API 모드(GET /about/gemma). */

test("what Gemma does page explains each step without inventing counts in sample mode", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: /Gemma가 하는 일|What Gemma does/ }).first().click();
  await expect(page).toHaveURL(/\/about\/gemma$/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(/Gemma가 하는 일|What Gemma does/);
  const table = page.getByRole("table");
  await expect(table.getByRole("row")).toHaveCount(7);                        // 머리 + 단계 여섯
  await expect(table.getByText(/리스크 분류|Risk labels/)).toBeVisible();
  await expect(page.getByText(/예시 데이터로 보는 중|viewing sample data/)).toBeVisible();
  await expect(table.getByRole("columnheader", { name: /Gemma 결과|Gemma results/ })).toHaveCount(0);
});
