import { expect, test } from "@playwright/test";

/* 만들기(Plan 20) — 예시 모드. 제품 한 줄과 시장 둘을 넣으면 시장마다 한 열: 고른 밈(원문 그대로) → 카피 → 다시 검사 → 포스터 구성, 그리고 사람의 승인.
   예시 모드는 모델 없이 고정 예시 제품으로 돈다. */

test("a pitch and two markets make one draft column per market, and only approved drafts are copied", async ({ page }) => {
  await page.goto("/?regions=KR,JP");
  const markets = page.getByRole("group", { name: /^(시장|Markets)/ });
  await expect(markets.getByRole("checkbox", { checked: true })).toHaveCount(2);
  await page.getByLabel(/한 줄 소개|One-line pitch/).fill("여름 한정 아이스 흑당 라떼");
  await page.getByRole("button", { name: /시장별 초안 만들기|Draft for each market/ }).click();

  const kr = page.getByRole("region", { name: /^(한국|South Korea|Korea)$/ });
  await expect(kr.getByText(/초안 완성|Draft ready/)).toBeVisible();
  await expect(kr.getByRole("heading", { name: /^(카피|Copy)$/ })).toBeVisible();
  await expect(kr.getByRole("heading", { name: /^(다시 검사|Check)$/ })).toBeVisible();
  await expect(page.getByRole("region", { name: /^(일본|Japan)$/ })).toBeVisible();      // 밈이 없어도 열은 남고 길을 알린다

  const copy = page.getByRole("button", { name: /승인한 초안 복사|Copy approved drafts/ });
  await expect(copy).toBeDisabled();
  await kr.getByRole("button", { name: /이 초안 승인|Approve this draft/ }).click();
  await expect(kr.getByRole("button", { name: /승인함|Approved/ })).toHaveAttribute("aria-pressed", "true");
  await expect(copy).toBeEnabled();
});

test("more than three markets are refused with a reason", async ({ page }) => {
  await page.goto("/?regions=KR,JP,TW");
  await page.getByRole("group", { name: /^(시장|Markets)/ }).getByText(/^(태국|Thailand)/).click();
  await expect(page.getByRole("group", { name: /^(시장|Markets)/ }).getByRole("alert")).toHaveText(/세 곳까지|Up to three/);
});
