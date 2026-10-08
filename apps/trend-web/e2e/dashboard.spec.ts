import { expect, test } from "@playwright/test";

/* 둘러보기(/trends, Plan 20 시안 r-stage) — 예시 모드. 시장 하나의 무대: 한국·일본·영어권 가운데 하나, 목록은 대시보드 규칙(Plan 04) 셋:
   지금 쓰는 말·식는 말·조심할 말. 말을 고르면 오른쪽 무대에 크게 서고, '자세히 보기' 는 그 시장을 들고 사전 항목으로 간다. */

test("one market at a time: market switch, the three lists and an entry", async ({ page }) => {
  await page.goto("/trends?m=JP");
  const markets = page.getByRole("navigation", { name: /^(시장|Markets)$/ });
  await expect(markets.getByRole("link")).toHaveCount(3);
  await expect(markets.getByRole("link", { name: /^(일본|Japan)/ })).toHaveAttribute("aria-current", "page");
  const lists = page.getByRole("navigation", { name: /^(목록|Lists)$/ });
  await expect(lists.getByRole("link")).toHaveCount(3);

  await page.getByRole("button", { name: /推し活/ }).first().click();
  await page.getByRole("link", { name: /^(자세히 보기|Open entry)/ }).first().click();
  await expect(page).toHaveURL(/\/dictionary\/t_oshikatsu\?m=JP$/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("推し活");
});

test("old addresses from the map, country and briefing pages still pick the market and list", async ({ page }) => {
  await page.goto("/trends?regions=JP&list=caution");
  await expect(page.getByRole("navigation", { name: /^(시장|Markets)$/ }).getByRole("link", { name: /^(일본|Japan)/ })).toHaveAttribute("aria-current", "page");
  await expect(page.getByRole("navigation", { name: /^(목록|Lists)$/ }).getByRole("link", { name: /^(조심할 말|Use with care)/ })).toHaveAttribute("aria-current", "page");
});

test("the primary action carries the market to the drafts", async ({ page }) => {
  await page.goto("/trends?m=KR");
  await expect(page.getByRole("link", { name: /^(한국 초안 만들기|Draft for Korea)$/ })).toHaveAttribute("href", "/?m=KR");
});

test("the phone layout never scrolls sideways", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/trends?m=KR");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  const [scroll, client] = await page.evaluate(() => [document.documentElement.scrollWidth, document.documentElement.clientWidth]);
  expect(scroll).toBeLessThanOrEqual(client);
});
