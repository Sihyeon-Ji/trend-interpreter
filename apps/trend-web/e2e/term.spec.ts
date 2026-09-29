import { expect, test } from "@playwright/test";

/* 사전 항목(화면 개편 2차: term) — 예시 데이터로 모델·서버 없이 */

test("entry answers 'can I use it' first and leads to making content", async ({ page }) => {
  await page.goto("/dictionary/t_luckyvicky");
  await expect(page).toHaveTitle(/^럭키비키 · (사전|Dictionary)/);
  const h1 = page.getByRole("heading", { level: 1 });
  await expect(h1).toHaveText("럭키비키");
  await expect(h1.locator("[lang=ko]")).toHaveCount(1);

  // 요약이 본문 절보다 먼저 나온다(휴대폰·화면 읽기 순서), 쓸 때 조심 줄은 늘 있다
  const summary = page.getByRole("complementary", { name: /요약|Summary/ });
  await expect(summary).toBeVisible();
  await expect(summary.getByText(/쓸 때 조심|Watch out/)).toBeVisible();
  const order = await page.evaluate(() => {
    const s = document.getElementById("term-summary");
    const usage = document.getElementById("usage");
    return !!s && !!usage && !!(s.compareDocumentPosition(usage) & Node.DOCUMENT_POSITION_FOLLOWING);
  });
  expect(order).toBe(true);

  // 절 제목에 번호가 없다
  for (const h of await page.getByRole("heading", { level: 2 }).allTextContents()) expect(h).not.toMatch(/^\d+\./);

  const make = page.getByRole("link", { name: /이 밈으로 만들기|Create with this meme/ });
  await expect(make).toHaveAttribute("href", "/recommend?term=t_luckyvicky");
});

test("an entry under review says so and offers no make button", async ({ page }) => {
  await page.goto("/dictionary/t_galau");
  await expect(page.getByText(/아직 확인 중인 설명입니다|still being reviewed/)).toBeVisible();
  await expect(page.getByRole("link", { name: /이 밈으로 만들기|Create with this meme/ })).toHaveCount(0);
});

test("the button is hidden when opened from meme ideas", async ({ page }) => {
  await page.goto("/dictionary/t_luckyvicky?from=recommend");
  await expect(page.getByRole("link", { name: /이 밈으로 만들기|Create with this meme/ })).toHaveCount(0);
});

test("an unknown word says what to do next", async ({ page }) => {
  await page.goto("/dictionary/t_no_such_word");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(/사전에 없는 말입니다|Not in the dictionary/);
  await expect(page.getByRole("link", { name: /메시지 해석으로|Explain a message/ })).toHaveAttribute("href", "/explain");
});

test("the phone layout never scrolls sideways", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/dictionary/t_crumbl");
  const width = await page.evaluate(() => document.documentElement.scrollWidth);
  expect(width).toBeLessThanOrEqual(390);
  await expect(page.getByRole("link", { name: /이 밈으로 만들기|Create with this meme/ })).toBeVisible();   // 요약 바로 아래 전폭 버튼
});
