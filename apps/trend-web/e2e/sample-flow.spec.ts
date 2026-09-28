import { expect, test } from "@playwright/test";

test("sample trend board and dictionary open without a model", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveTitle(/Trend Interpreter/);
  await expect(page.getByRole("main")).toBeVisible();

  await page.goto("/dictionary");
  await expect(page).toHaveURL(/\/dictionary$/);
  await expect(page.getByRole("main")).toBeVisible();
});

test("keyword dashboard filters by region and opens a card", async ({ page }) => {
  await page.goto("/trends");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

  // 일본을 고르면 일본에서 쓰이는 것만 남는다: 推し活 은 있고, 한국에서만 쓰는 자만추 는 빠진다
  await page.getByRole("navigation", { name: /지역|Regions/ }).getByRole("link", { name: /^(일본|Japan) \d+$/ }).click();
  await expect(page).toHaveURL(/regions=JP$/);
  const card = page.getByRole("article").filter({ hasText: "推し活" });
  await expect(card).toHaveCount(1);
  await expect(page.getByRole("article").filter({ hasText: "자만추" })).toHaveCount(0);

  await card.getByRole("link", { name: "推し活" }).click();
  await expect(page).toHaveURL(/\/dictionary\/t_oshikatsu$/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("推し活");
});

test("recommend suggests memes for a product without a model", async ({ page }) => {
  await page.goto("/recommend");
  await page.getByLabel(/홍보 문구|Your copy/).fill("여름 한정 아이스 라떼");
  await page.getByRole("button", { name: /밈 추천받기|Suggest memes/ }).click();

  await expect(page.getByRole("heading", { name: /추천 밈|Suggested memes/ })).toBeVisible();
  await expect(page.getByText(/예시 제품|sample product/)).toBeVisible();          // 모델 없는 환경임을 숨기지 않는다
  const items = page.getByRole("article");
  await expect(items.filter({ hasText: "럭키비키" })).toHaveCount(1);
  await expect(items.filter({ hasText: "aura farming" })).toHaveCount(0);        // 친근한 톤에는 비꼬는 말투를 넣지 않는다

  await items.filter({ hasText: "럭키비키" }).getByRole("link", { name: /사전에서 보기|Open in dictionary/ }).click();
  await expect(page).toHaveURL(/\/dictionary\/t_luckyvicky$/);
});
