import { expect, test } from "@playwright/test";

test("dashboard, world map and dictionary open without a model", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveTitle(/Trend Interpreter/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(/트렌드 대시보드|Trend dashboard/);   // 첫 화면은 대시보드(디자인 개편 09-29)
  await expect(page.getByRole("navigation", { name: /메뉴|Menu/ }).first()).toBeVisible();

  await page.goto("/map");
  await expect(page.getByRole("main")).toBeVisible();
  await page.goto("/dictionary");
  await expect(page).toHaveURL(/\/dictionary$/);
  await expect(page.getByRole("main")).toBeVisible();
});

test("keyword dashboard filters by region and opens an entry", async ({ page }) => {
  await page.goto("/trends");                                                     // 예전 주소는 첫 화면으로 넘어간다
  await expect(page).toHaveURL(/\/$/);

  // 일본을 고르면 일본에서 쓰이는 것만 남는다: 推し活 은 있고, 한국에서만 쓰는 자만추 는 빠진다
  await page.getByRole("navigation", { name: /지역|Regions/ }).getByRole("link", { name: /^(일본|Japan) \d+$/ }).click();
  await expect(page).toHaveURL(/regions=JP/);
  const table = page.getByRole("table");
  await expect(table.getByRole("link", { name: "推し活" })).toHaveCount(1);
  await expect(table.getByRole("link", { name: "자만추" })).toHaveCount(0);

  await table.getByRole("link", { name: "推し活" }).click();
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

  // 사전은 새 탭으로 연다 — 추천 결과가 남아 있어야 한다
  const [tab] = await Promise.all([
    page.waitForEvent("popup"),
    items.filter({ hasText: "럭키비키" }).getByRole("link", { name: /사전에서 보기|Open in dictionary/ }).click(),
  ]);
  await expect(tab).toHaveURL(/\/dictionary\/t_luckyvicky$/);
  await expect(page.getByRole("heading", { name: /추천 밈|Suggested memes/ })).toBeVisible();
});

test("drafts copy and a script from a recommended meme without a model", async ({ page }) => {
  await page.goto("/recommend");
  await page.getByLabel(/홍보 문구|Your copy/).fill("여름 한정 아이스 라떼");
  await page.getByRole("button", { name: /밈 추천받기|Suggest memes/ }).click();
  const item = page.getByRole("article").filter({ hasText: "럭키비키" });
  await item.getByRole("checkbox", { name: /만들기에 쓰기|Use for drafts/ }).check();
  await page.getByRole("button", { name: /카피·대본 만들기|Draft copy and script/ }).click();

  await expect(page.getByRole("heading", { name: /만든 결과물|Drafts/ })).toBeVisible();
  await expect(page.getByText(/AI가 만든 초안|AI-generated drafts/)).toBeVisible();      // 게시 전 확인 안내
  await expect(page.getByRole("heading", { name: /숏폼 대본|Short-form script/ })).toBeVisible();
  // 복사 버튼마다 무엇을 복사하는지 이름이 있다 — 썸네일 구성안에도 있다
  await expect(page.getByRole("button", { name: /^(복사|Copy): (인스타그램|Instagram) 1$/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /^(복사|Copy): (썸네일 구성안|Thumbnail plan)$/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: /만든 결과물|Drafts/ })).toBeFocused();       // 결과가 오면 그 제목으로 초점을 옮긴다
});
