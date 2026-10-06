import { expect, test } from "@playwright/test";

/* 사전 항목(화면 개편 2차: term) — 예시 데이터로 모델·서버 없이 */

test("entry answers 'can I use it' first and leads to making content", async ({ page }) => {
  await page.goto("/dictionary/t_luckyvicky");
  await expect(page).toHaveTitle(/^럭키비키 · (사전|Dictionary)/);
  const h1 = page.getByRole("heading", { level: 1 });
  await expect(h1).toHaveText("럭키비키");
  await expect(h1).toHaveAttribute("lang", "ko");                       // 원문에 lang — 제목 자체가 원문이다

  // 지금 상태(단계·퍼진 정도·브랜드 리스크·4주 언급·마지막 쓰임)가 본문 줄보다 먼저 나온다(휴대폰·화면 읽기 순서). 리스크 칸은 늘 있다
  const vitals = page.getByRole("definition").first().locator("xpath=ancestor::dl");
  await expect(vitals.getByText(/브랜드 리스크|Brand risk/)).toBeVisible();
  const order = await page.evaluate(() => {
    const v = document.querySelector("dl.n-vitals");
    const usage = document.getElementById("usage");
    return !!v && !!usage && !!(v.compareDocumentPosition(usage) & Node.DOCUMENT_POSITION_FOLLOWING);
  });
  expect(order).toBe(true);
  // 누가 정했나 — 규칙·모델·사람 표지
  await expect(page.getByRole("complementary", { name: /누가 정했나|Who decided/ })).toBeVisible();

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

test("a nuance not checked against sources says so; a human-reviewed one does not", async ({ page }) => {
  await page.goto("/dictionary/t_aurafarming");
  const usage = page.locator("section", { has: page.locator("#usage") });
  await expect(usage.getByText(/근거 미확인|Not checked against sources/)).toBeVisible();
  await page.goto("/dictionary/t_luckyvicky");
  await expect(page.locator("section", { has: page.locator("#usage") }).getByText(/근거 미확인|Not checked against sources/)).toHaveCount(0);
});
