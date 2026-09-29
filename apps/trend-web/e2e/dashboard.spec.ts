import { expect, test } from "@playwright/test";

/* 대시보드(디자인 개편 2차 검토 09-29) — 예시 모드. 지역은 하나만, 주의 밈은 쓰이는·식는 목록에도 남고 사용 자제는 주의에만(Plan 04),
   행 전체가 링크, 빈 지역은 패널 하나. */

const count = (name: string) => Number(name.match(/(\d+)\s*$/)?.[1] ?? NaN);

test("region chips pick one region and tab counts match the chip", async ({ page }) => {
  await page.goto("/?regions=JP");
  const chips = page.getByRole("navigation", { name: /^(지역|Regions)$/ });
  await expect(chips.locator("[aria-current='true']")).toHaveCount(1);
  const jp = count(await chips.getByRole("link", { name: /^(일본|Japan) \d+$/ }).innerText());

  const tabs = page.getByRole("navigation", { name: /밈 목록|Meme lists/ }).getByRole("link");
  const names = await tabs.allInnerTexts();
  expect(names).toHaveLength(3);
  const [rising, fading, caution] = names.map(count);
  expect(rising + fading).toBeLessThanOrEqual(jp);                     // 칩 건수 = 쓰이는 + 식는 + 사용 자제(주의 목록에만)
  expect(jp).toBeLessThanOrEqual(rising + fading + caution);

  await chips.getByRole("link", { name: /^(대만|Taiwan) \d+$/ }).click();
  await expect(page).toHaveURL(/[?&]regions=TW(&|$)/);                  // 더하지 않고 바꾼다
  await expect(chips.locator("[aria-current='true']")).toHaveCount(1);
});

test("one primary action carries the region to recommend", async ({ page }) => {
  await page.goto("/?regions=JP");
  const header = page.locator("header").filter({ has: page.getByRole("heading", { level: 1 }) });
  await expect(header.getByRole("link", { name: /내 제품에 맞는 밈 추천받기|Get meme picks for my product/ })).toHaveAttribute("href", "/recommend?regions=JP");
  await expect(header.getByRole("link", { name: /지도에서 지역 고르기|Pick a region on the map/ })).toHaveAttribute("href", "/map?region=JP");
});

test("the whole row opens the dictionary entry", async ({ page }) => {
  await page.goto("/?regions=JP");
  const row = page.getByRole("table").getByRole("row").filter({ has: page.getByRole("link", { name: "推し活" }) });
  // 표제어 글자가 아니라 단계 칸을 눌러도 — 링크의 ::after 가 행을 덮어 그 자리를 누르면 링크가 받는다(그래서 force)
  await row.getByRole("cell").nth(1).click({ force: true });
  await expect(page).toHaveURL(/\/dictionary\/t_oshikatsu$/);
});

test("an empty region shows one panel with a way out", async ({ page }) => {
  await page.goto("/?regions=HK");
  await expect(page.getByRole("navigation", { name: /밈 목록|Meme lists/ })).toHaveCount(0);
  await expect(page.getByRole("table")).toHaveCount(0);
  await page.getByRole("link", { name: /전체 지역 보기|View all regions/ }).click();
  await expect(page).toHaveURL(/regions=all/);
  await expect(page.getByRole("table")).toBeVisible();
});

test("a page past the end goes to the last page", async ({ page }) => {
  await page.goto("/?regions=all&page=99");
  await expect(page).toHaveURL(/regions=all(&page=\d+)?$/);
  await expect(page).not.toHaveURL(/page=99/);
  await expect(page.getByText(/\d+개 중 \d+–\d+|\d+–\d+ of \d+/)).toBeVisible();
});

test("the phone layout never scrolls sideways", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(page.getByRole("main").getByRole("list").last()).toBeVisible();
  const [scroll, client] = await page.evaluate(() => [document.documentElement.scrollWidth, document.documentElement.clientWidth]);
  expect(scroll).toBeLessThanOrEqual(client);
});
