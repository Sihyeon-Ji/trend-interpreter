import { expect, test } from "@playwright/test";

/* 최근 변화·나라 화면 (화면 개편 2차 feeds). 예시 모드: lib/sample/updates.ts */

test("recent changes shows only user-facing changes and filters by kind and region", async ({ page }) => {
  await page.goto("/updates");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(/최근 변화|Recent changes/);
  const tabs = page.getByRole("navigation", { name: /변화 종류|Kinds of change/ });
  await expect(tabs.getByRole("link", { name: /^(전체|All) 6$/ })).toBeVisible();
  const table = page.getByRole("table");
  await expect(table.getByRole("link", { name: "推し活" })).toHaveAttribute("href", "/dictionary/t_oshikatsu");
  await expect(table.getByText(/다시 확인|Re-checked|확인 대기|awaiting review/)).toHaveCount(0);   // 작업 기록은 이용자 피드에 없다

  await tabs.getByRole("link", { name: /^(검색 급증|Search spikes) 3$/ }).click();
  await expect(page).toHaveURL(/kind=spike/);
  await expect(table.getByRole("link", { name: "推し活" })).toHaveCount(0);
  // 검색 급증은 그 나라 화면의 이유 행으로 곧장 간다
  await table.getByRole("link", { name: "八つ墓村" }).click();
  await expect(page).toHaveURL(/\/country\/JP\?tab=why#why-/);
  await expect(page.locator("li[id^='why-']", { hasText: "八つ墓村" })).toBeVisible();

  await page.goto("/updates?regions=KR");
  await expect(page.getByRole("table").getByRole("link", { name: "八つ墓村" })).toHaveCount(0);
  await expect(page.getByRole("table").getByRole("link", { name: "삐에로 밈" })).toHaveCount(1);
});

test("country page splits memes, searches and reasons into tabs", async ({ page }) => {
  await page.goto("/country/JP");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(/일본|Japan/);
  await expect(page.getByRole("link", { name: /일본 밈으로 추천받기|Get meme ideas for Japan/ })).toHaveAttribute("href", "/recommend?regions=JP");
  await expect(page.getByRole("table").getByRole("link", { name: "推し活" })).toHaveAttribute("href", "/dictionary/t_oshikatsu");
  await expect(page.getByText(/세대 분포|Generations using/)).toHaveCount(0);

  const tabs = page.getByRole("navigation", { name: /나라 화면 목록|Country lists/ });
  await tabs.getByRole("link", { name: /지금 뜨는 검색어|Trending searches/ }).click();
  await expect(page.getByRole("table").getByRole("columnheader", { name: /검색 증가|Search growth/ })).toBeVisible();

  await tabs.getByRole("link", { name: /검색이 늘어난 이유|Why searches spiked/ }).click();
  await expect(page.getByText(/이유를 아직 찾지 못한 검색어 1개|1 searches with no clear reason/)).toBeVisible();   // 원인 미확인은 빼고 건수만
  await expect(page.getByText("森本レオ")).toHaveCount(0);
});

test("country page: outside target regions shows searches only, unknown codes are 404", async ({ page }) => {
  await page.goto("/country/US");
  await expect(page.getByRole("link", { name: /밈으로 추천받기|Get meme ideas/ })).toHaveCount(0);
  await expect(page.getByRole("navigation", { name: /나라 화면 목록|Country lists/ }).getByRole("link", { name: /지금 쓰이는 밈|In use now/ })).toHaveCount(0);
  const res = await page.goto("/country/ZZ");
  expect(res?.status()).toBe(404);
});
