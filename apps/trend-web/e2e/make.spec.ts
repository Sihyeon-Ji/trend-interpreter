import { expect, test } from "@playwright/test";

/* 만들기(Plan 20, 시안 r-stage '무대') — 예시 모드. 제품 한 줄과 시장(한국·일본·영어권)을 넣으면 /drafts 에서 시장마다 초안:
   규칙이 고른 말과 뺀 말 → AI가 쓴 문구 → 규칙 재검사 → 사람 승인. 예시 모드는 모델 없이 고정 예시 제품으로 돈다.
   승인·검수 요청은 로그인한 사람만 한다 — 그 장면은 approvals.spec.ts */

test("a pitch makes one draft per market, with rule, AI and reviewer steps, and asks a visitor to sign in before approval", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("button", { name: /시장 포함$|^Include /, pressed: true })).toHaveCount(3);
  await page.getByRole("textbox", { name: /^(제품|Product)$/ }).fill("여름 한정 아이스 흑당 라떼");
  await page.getByRole("button", { name: /^(초안 만들기|Create drafts)$/ }).click();
  await expect(page).toHaveURL(/\/drafts$/);

  const kr = page.getByRole("article", { name: /^(한국|Korea)$/ });
  await expect(kr.getByRole("list", { name: /^(한국|Korea), (초안이 만들어지는 순서|How a draft is made)$/ })).toBeVisible();
  // 식어 가는 말은 고르지 않고 '뺀 말' 에 이유와 함께 남는다(규칙이 고른 말을 규칙이 다시 막는 모순이 없게)
  await expect(kr.getByRole("heading", { name: /(뺀 말|Left out)$/ })).toBeVisible();

  // 로그인하지 않은 사람의 문구는 서버에 쌓지 않는다 — 승인·요청 단추 대신 로그인 안내만
  await expect(kr.getByText(/로그인하면 검수를 요청할 수 있어요|Sign in to request a review/)).toBeVisible({ timeout: 30_000 });
  await expect(kr.getByRole("link", { name: /^(로그인|Sign in)$/ })).toHaveAttribute("href", "/login?next=/drafts");
  await expect(kr.getByRole("button", { name: /초안 승인|검수 요청|Approve the|Request review/ })).toHaveCount(0);
  await expect(page.getByText(/\d개 시장 중 0곳 승인|0 of \d markets approved/).first()).toBeVisible();
});

test("submitting without a market or a product says what is missing", async ({ page }) => {
  await page.goto("/");
  const on = page.getByRole("button", { name: /시장 포함$|^Include /, pressed: true });
  for (let i = 0; i < 3; i++) await on.first().click();   // 고른 셋을 모두 뺀다
  await expect(on).toHaveCount(0);
  await page.getByRole("button", { name: /^(초안 만들기|Create drafts)$/ }).click();
  await expect(page.getByRole("alert").filter({ hasText: /시장을 하나 이상|at least one market/ })).toBeVisible();
});
