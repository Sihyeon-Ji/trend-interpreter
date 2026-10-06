import { expect, test } from "@playwright/test";

/* 둘러보기(/trends, Plan 20 시안 n-redesign) — 예시 모드. 시장은 하나씩(한국·일본·영어권 탭, 다른 나라는 들어온 나라를 탭에 더한다).
   낱말 크기는 그 시장 안의 순위로만, 목록은 대시보드 규칙(Plan 04) 셋: 쓰이는 중·식는 중·조심할 말. */

test("one market at a time: tabs, word field and the three lists", async ({ page }) => {
  await page.goto("/trends?regions=JP");
  const tabs = page.getByRole("navigation", { name: /^(시장|Markets)$/ });
  await expect(tabs.getByRole("link", { name: /^(일본|Japan)/ })).toHaveAttribute("aria-current", "page");
  await expect(tabs.getByRole("link")).toHaveCount(3);
  for (const name of [/^(쓰이는 중|In use)/, /^(식는 중|Fading)/, /^(조심할 말|Use with care)/]) {
    await expect(page.getByRole("heading", { level: 2, name })).toBeVisible();
  }
  // 낱말을 누르면 그 시장을 들고 사전 항목으로
  await page.locator(".n-field-words").getByRole("link", { name: "推し活" }).click();
  await expect(page).toHaveURL(/\/dictionary\/t_oshikatsu\?regions=JP$/);
});

test("the primary action carries the market to the drafts", async ({ page }) => {
  await page.goto("/trends?regions=KR");
  await expect(page.getByRole("link", { name: /이 시장으로 초안 만들기|Draft for this market/ })).toHaveAttribute("href", "/?regions=KR");
  await expect(page.getByRole("link", { name: /지도에서 지역 고르기|Pick a region on the map/ })).toHaveAttribute("href", "/map?regions=KR");
});

test("a country from the map gets its own tab, and an empty one says so", async ({ page }) => {
  await page.goto("/trends?regions=HK");
  const tabs = page.getByRole("navigation", { name: /^(시장|Markets)$/ });
  await expect(tabs.getByRole("link")).toHaveCount(4);
  await expect(tabs.getByRole("link", { name: /^(홍콩|Hong Kong)/ })).toHaveAttribute("aria-current", "page");
  await expect(page.getByText(/해당하는 말이 없습니다|Nothing here for/).first()).toBeVisible();
});

test("a page past the end goes to the last page", async ({ page }) => {
  await page.goto("/trends?regions=KR&page=99");
  await expect(page).not.toHaveURL(/page=99/);
});

test("the phone layout never scrolls sideways", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/trends?regions=KR");
  await expect(page.getByRole("table").first()).toBeVisible();
  const [scroll, client] = await page.evaluate(() => [document.documentElement.scrollWidth, document.documentElement.clientWidth]);
  expect(scroll).toBeLessThanOrEqual(client);
});
