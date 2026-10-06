import { expect, test } from "@playwright/test";

/* 만들기(Plan 20, '누가 정했나' 원장) — 예시 모드. 제품 한 줄과 시장(한국·일본·영어권)을 넣으면 시장마다 초안:
   규칙이 고른 말과 뺀 말 → 모델이 쓴 카피 → 규칙 재검사 → 포스터 구성 → 검수자 승인. 예시 모드는 모델 없이 고정 예시 제품으로 돈다. */

test("a pitch makes one draft per market, with rule, model and reviewer marks, and approval is tallied", async ({ page }) => {
  await page.goto("/");
  const markets = page.getByRole("group", { name: /^(시장|Markets)/ });
  await expect(markets.getByRole("button", { pressed: true })).toHaveCount(3);
  await page.getByLabel(/한 줄 설명|One-line description/).fill("여름 한정 아이스 흑당 라떼");
  await page.getByRole("button", { name: /시장별 초안 만들기|Draft for each market/ }).click();

  const kr = page.getByRole("region", { name: /^(한국|Korea)$/ });
  await expect(kr.getByRole("list", { name: /초안이 만들어진 순서|How the .* draft was made/ })).toBeVisible();
  await expect(kr.getByText(/규칙 확인|Rule check/).first()).toBeVisible();
  // 식어 가는 말은 고르지 않고 '뺀 말' 에 이유와 함께 남는다(규칙이 고른 말을 규칙이 다시 막는 모순이 없게)
  await expect(kr.getByRole("heading", { name: /뺀 말|Left out/ })).toBeVisible();
  await expect(page.getByRole("region", { name: /^(일본|Japan)$/ }).getByText(/맞는 말 없음|No fitting word/).first()).toBeVisible();

  await kr.getByRole("button", { name: /한국 초안 승인|Approve Korea draft/ }).click();
  await expect(kr.getByText(/검수자 승인|Approved by Reviewer/)).toBeVisible();
  await expect(page.getByText(/1개 시장 중 1개 승인|1 of 1 markets approved/)).toBeVisible();
});

test("submitting without a market or a product says what is missing", async ({ page }) => {
  await page.goto("/");
  const markets = page.getByRole("group", { name: /^(시장|Markets)/ });
  for (let i = 0; i < 3; i++) await markets.getByRole("button", { pressed: true }).first().click();   // 고른 셋을 모두 뺀다
  await expect(markets.getByRole("button", { pressed: true })).toHaveCount(0);
  await page.getByRole("button", { name: /시장별 초안 만들기|Draft for each market/ }).click();
  await expect(page.getByRole("alert").filter({ hasText: /시장을 하나 이상|at least one market/ })).toBeVisible();
});
