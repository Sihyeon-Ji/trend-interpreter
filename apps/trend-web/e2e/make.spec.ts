import { expect, test } from "@playwright/test";

/* 만들기(Plan 20, 시안 r-stage '무대') — 예시 모드. 제품 한 줄과 시장(한국·일본·영어권)을 넣으면 /drafts 에서 시장마다 초안:
   규칙이 고른 말과 뺀 말 → AI가 쓴 문구 → 규칙 재검사 → 사람 승인. 예시 모드는 모델 없이 고정 예시 제품으로 돈다. */

test("a pitch makes one draft per market, with rule, AI and reviewer steps, and approval is tallied", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("button", { name: /시장 포함$|^Include /, pressed: true })).toHaveCount(3);
  await page.getByRole("textbox", { name: /^(제품|Product)$/ }).fill("여름 한정 아이스 흑당 라떼");
  await page.getByRole("button", { name: /^(초안 만들기|Create drafts)$/ }).click();
  await expect(page).toHaveURL(/\/drafts$/);

  const kr = page.getByRole("article", { name: /^(한국|Korea)$/ });
  await expect(kr.getByRole("list", { name: /^(한국|Korea), (초안이 만들어지는 순서|How a draft is made)$/ })).toBeVisible();
  // 식어 가는 말은 고르지 않고 '뺀 말' 에 이유와 함께 남는다(규칙이 고른 말을 규칙이 다시 막는 모순이 없게)
  await expect(kr.getByRole("heading", { name: /(뺀 말|Left out)$/ })).toBeVisible();

  const approve = kr.getByRole("button", { name: /한국 초안 승인|Approve the Korea draft/ });
  await expect(approve).toBeEnabled({ timeout: 30_000 });
  await approve.click();
  await expect(page.getByText(/\d개 시장 중 1곳 승인|1 of \d markets approved/).first()).toBeVisible();
});

test("submitting without a market or a product says what is missing", async ({ page }) => {
  await page.goto("/");
  const on = page.getByRole("button", { name: /시장 포함$|^Include /, pressed: true });
  for (let i = 0; i < 3; i++) await on.first().click();   // 고른 셋을 모두 뺀다
  await expect(on).toHaveCount(0);
  await page.getByRole("button", { name: /^(초안 만들기|Create drafts)$/ }).click();
  await expect(page.getByRole("alert").filter({ hasText: /시장을 하나 이상|at least one market/ })).toBeVisible();
});
