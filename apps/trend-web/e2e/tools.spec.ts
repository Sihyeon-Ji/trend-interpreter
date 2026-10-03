import { expect, test } from "@playwright/test";

/* 마케터가 밈으로 할 일 셋 — 첫 화면의 '무엇을 만들까요?', 트렌드 브리핑, 카피 검사. 예시 모드(모델·서버 없음). */

test("home shows the three tools and carries the picked regions", async ({ page }) => {
  await page.goto("/?regions=JP");
  const tools = page.getByRole("region", { name: /무엇을 만들까요|What do you want to make/ });
  await expect(tools.getByRole("link", { name: /캠페인 키트|Campaign kit/ })).toHaveAttribute("href", "/recommend?regions=JP");
  await expect(tools.getByRole("link", { name: /트렌드 브리핑 보고서|Trend briefing report/ })).toHaveAttribute("href", "/briefing?regions=JP");
  await expect(tools.getByRole("link", { name: /카피 검사|Copy check/ })).toHaveAttribute("href", "/check?regions=JP");
  // 검정 버튼은 머리의 '추천받기' 하나 — 도구 카드는 테두리만
  for (const link of await tools.getByRole("link").all()) await expect(link).not.toHaveClass(/bg-ink/);
});

test("briefing lists the market on one page with a rule summary, print and share", async ({ page }) => {
  await page.goto("/briefing?regions=KR");
  await expect(page.getByRole("heading", { level: 1, name: /트렌드 브리핑|Trend briefing/ })).toBeVisible();
  for (const name of [/지금 써도 되는 밈|Use now/, /조심해서 쓸 밈|Use with care/, /쓰지 말 밈|Avoid/, /식어 가는 밈|Fading/]) {
    await expect(page.getByRole("heading", { level: 2, name })).toBeVisible();
  }
  const summary = page.getByRole("region", { name: /^(요약|Summary)$/ });
  await expect(summary).toContainText(/한국에서 지금 쓰이는 밈은 \d+개|memes are in use in Korea/);
  await expect(summary).toContainText(/목록과 건수로 만든 요약|Built from the lists and counts/);   // 예시 모드는 모델이 없다
  await expect(page.getByRole("button", { name: /PDF로 저장|Save as PDF/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /링크 복사|Copy link/ })).toBeVisible();

  // 지역 칩은 브리핑 안에서 움직인다
  await page.getByRole("navigation", { name: /^(지역|Regions)$/ }).getByRole("link", { name: /^(일본|Japan)/ }).click();
  await expect(page).toHaveURL(/\/briefing\?regions=KR,JP$/, { timeout: 15_000 });
});

test("copy check flags memes by rules and never pretends to check the meaning without a model", async ({ page }) => {
  await page.goto("/check?regions=KR");
  await page.getByRole("button", { name: /^(검사하기|Check)$/ }).click();
  // Next 의 화면 전환 안내(#__next-route-announcer__)도 alert 다 — 폼 안의 것만 본다
  await expect(page.locator("form").getByRole("alert")).toContainText(/검사할 문구를 넣어 주세요|Paste the copy to check/);

  await page.getByLabel(/검사할 문구|Copy to check/).fill("아 샤갈 오늘 점심 뭐 먹지");
  await page.getByRole("button", { name: /^(검사하기|Check)$/ }).click();
  const result = page.getByRole("region", { name: /찾은 밈 \d+개|memes found/ });
  await expect(result).toContainText("샤갈");
  await expect(result).toContainText(/조심해서 쓰세요|Use with care/);
  await expect(result).toContainText(/뜻에 맞게 썼는지는 보지 않았습니다|meaning was not checked/);
});

test("briefing and copy check fit a phone screen", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  for (const url of ["/briefing?regions=KR", "/check"]) {
    await page.goto(url);
    const wide = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
    expect(wide).toBe(false);
  }
});
