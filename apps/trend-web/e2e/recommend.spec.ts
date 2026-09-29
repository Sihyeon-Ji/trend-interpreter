import { expect, test } from "@playwright/test";

/* 밈 추천 화면 개편(2차) — 예시 모드(모델 없이)에서 끝까지. docs/트렌드/디자인-개편.md */

const primary = "main [data-slot=button][data-variant=default]";

test("reads ?regions= and carries a meme picked in the dictionary (?term=) into the drafts", async ({ page }) => {
  await page.goto("/recommend?regions=JP&term=t_oshikatsu");
  await expect(page.getByRole("checkbox", { name: "일본", exact: true })).toBeChecked();
  await expect(page.getByRole("checkbox", { name: "한국", exact: true })).not.toBeChecked();
  await expect(page.locator("form").getByText("推し活")).toBeVisible();

  await page.getByLabel(/홍보 문구/).fill("여름 한정 아이스 라떼");
  await page.getByRole("button", { name: "밈 추천받기" }).click();
  const row = page.getByRole("row").filter({ hasText: "推し活" });
  await expect(row.getByRole("checkbox", { name: "推し活 고르기" })).toBeChecked();   // 사전에서 고른 밈은 미리 골라 둔다
  await expect(row.locator('[lang="ja"]', { hasText: "推し活" })).toBeVisible();      // 표제어 원문에 lang
  await expect(page.getByText("고른 밈 1/3")).toBeVisible();

  await page.getByRole("button", { name: "카피·대본 만들기" }).click();
  await expect(page.getByRole("heading", { name: /만든 결과물/ })).toBeFocused();
  await expect(page.getByRole("table", { name: "쓴 밈" }).getByText("推し活")).toBeVisible();
});

test("black is only the next action, and the pick bar explains the limit", async ({ page }) => {
  await page.goto("/recommend?term=t_oshikatsu");
  await expect(page.locator(primary)).toHaveCount(1);
  await expect(page.locator(primary)).toHaveText("밈 추천받기");

  await page.getByLabel(/홍보 문구/).fill("여름 한정 아이스 라떼");
  await page.getByRole("button", { name: "밈 추천받기" }).click();
  await expect(page.getByRole("heading", { name: /추천 밈 \d+개/ })).toBeFocused();
  await expect(page.getByRole("button", { name: "다시 추천받기" })).toHaveAttribute("data-variant", "outline");
  await expect(page.locator(primary)).toHaveText("카피·대본 만들기");

  for (const name of ["럭키비키 고르기", "원영적 사고 고르기"]) await page.getByRole("checkbox", { name }).check();
  await expect(page.getByText("고른 밈 3/3")).toBeVisible();
  await expect(page.getByText(/3개까지 고를 수 있습니다/)).toBeVisible();

  await page.getByRole("button", { name: "카피·대본 만들기" }).click();
  await expect(page.getByRole("heading", { name: /만든 결과물/ })).toBeVisible();
  await expect(page.locator(primary)).toHaveCount(0);                       // 3단계에는 검정 버튼이 없다
  await page.getByRole("tab", { name: /숏폼 대본/ }).click();
  await expect(page.getByRole("columnheader", { name: "시간" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "0–4초" })).toBeVisible();

  // 밈 다시 고르기 — 고른 밈은 그대로
  await page.getByRole("button", { name: "밈 다시 고르기" }).click();
  await expect(page.getByRole("checkbox", { name: "럭키비키 고르기" })).toBeChecked();
});

test("tells when the input changed after suggestions", async ({ page }) => {
  await page.goto("/recommend");
  await page.getByLabel(/홍보 문구/).fill("여름 한정 아이스 라떼");
  await page.getByRole("button", { name: "밈 추천받기" }).click();
  await expect(page.getByRole("heading", { name: /추천 밈 \d+개/ })).toBeVisible();
  await expect(page.getByText(/입력이 바뀌었습니다/)).toHaveCount(0);
  await page.locator("label", { hasText: "재치" }).click();
  await expect(page.getByRole("radio", { name: "재치" })).toBeChecked();
  await expect(page.getByText(/입력이 바뀌었습니다/)).toBeVisible();
});

test("drafting shows elapsed time and can be stopped", async ({ page }) => {
  // 예시 모드는 바로 끝나므로 요청을 붙잡아 둔다 — 실제로는 10~85초
  await page.route("**/api/generate", async (route) => { await new Promise((r) => setTimeout(r, 4000)); await route.continue().catch(() => {}); });
  await page.goto("/recommend");
  await page.getByLabel(/홍보 문구/).fill("여름 한정 아이스 라떼");
  await page.getByRole("button", { name: "밈 추천받기" }).click();
  await page.getByRole("checkbox", { name: "럭키비키 고르기" }).check();
  await page.getByRole("button", { name: "카피·대본 만들기" }).click();
  await expect(page.getByText(/결과물을 만드는 중입니다/).first()).toBeVisible();
  await expect(page.getByText(/초 지남/)).toBeVisible();
  await expect(page.getByRole("button", { name: "그만두기" })).toBeFocused();
  await page.getByRole("button", { name: "그만두기" }).click();
  await expect(page.getByText(/만들기를 멈췄습니다/)).toBeVisible();
  await expect(page.getByRole("checkbox", { name: "럭키비키 고르기" })).toBeChecked();
});

test.describe("phone", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("results take focus, step 1 folds to a summary, and the page never scrolls sideways", async ({ page }) => {
    await page.goto("/recommend");
    await page.getByLabel(/홍보 문구/).fill("여름 한정 아이스 라떼");
    await page.getByRole("button", { name: "밈 추천받기" }).click();
    await expect(page.getByRole("heading", { name: /추천 밈 \d+개/ })).toBeFocused();
    await expect(page.getByLabel(/홍보 문구/)).toBeHidden();
    await expect(page.getByRole("button", { name: "고치기" })).toBeVisible();
    const wide = async () => page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(await wide()).toBeLessThanOrEqual(0);

    await page.getByRole("listitem").filter({ hasText: "럭키비키" }).getByRole("checkbox", { name: "럭키비키 고르기" }).check();
    await page.getByRole("button", { name: "카피·대본 만들기" }).click();
    await expect(page.getByRole("heading", { name: /만든 결과물/ })).toBeFocused();
    await page.getByRole("tab", { name: /숏폼 대본/ }).click();
    await expect(page.getByRole("heading", { name: "0–4초" })).toBeVisible();   // 휴대폰은 장면마다 블록
    expect(await wide()).toBeLessThanOrEqual(0);

    await page.getByRole("button", { name: "고치기" }).click();
    await expect(page.getByLabel(/홍보 문구/)).toBeVisible();
  });
});
