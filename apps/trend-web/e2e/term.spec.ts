import { expect, test } from "@playwright/test";

/* 사전 항목(Plan 20 시안 r-stage) — 예시 데이터로 모델·서버 없이. 원문 표기를 크게, 바로 아래 '써도 되나요', 그 아래 뜻·근거·기록 */

test("entry answers 'can I use it' first and leads to making a draft", async ({ page }) => {
  await page.goto("/dictionary/t_luckyvicky");
  await expect(page).toHaveTitle(/^럭키비키 — (트렌드 통역|Trend Interpreter)$/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("럭키비키");
  await expect(page.getByText(/^(써도 되나요|Can I use it)/).first()).toBeVisible();
  await expect(page.locator("#refs")).toHaveCount(1);                      // 다른 화면의 '#refs' 링크가 닿는 곳
  // 절 제목에 번호가 없다
  for (const h of await page.getByRole("heading", { level: 2 }).allTextContents()) expect(h).not.toMatch(/^\d+\./);
  await expect(page.getByRole("link", { name: /^(이 말로 초안 만들기|Draft with this word)$/ })).toHaveAttribute("href", "/?term=t_luckyvicky");
});

test("an entry under review is absent from the public dictionary", async ({ page }) => {
  await page.goto("/dictionary/t_galau");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(/이 말은 사전에 없어요|isn't in the dictionary/);
  await expect(page.getByRole("link", { name: /^(이 말로 초안 만들기|Draft with this word)$/ })).toHaveCount(0);
});

test("an unknown word says what to do next", async ({ page }) => {
  await page.goto("/dictionary/t_no_such_word");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(/이 말은 사전에 없어요|isn't in the dictionary/);
  await expect(page.getByRole("main").getByRole("link", { name: /^(둘러보기|Explore)$/ })).toHaveAttribute("href", "/trends");
});

test("model-estimated ages are absent from measured search-interest fields", async ({ page }) => {
  await page.goto("/dictionary/t_oshikatsu");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByText(/검색 관심이 확인된 세대|Age groups with measured search interest/)).toHaveCount(0);
});

test("the phone layout never scrolls sideways", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/dictionary/t_crumbl");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  const width = await page.evaluate(() => document.documentElement.scrollWidth);
  expect(width).toBeLessThanOrEqual(390);
});
