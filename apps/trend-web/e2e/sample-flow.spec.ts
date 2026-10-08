import { expect, test } from "@playwright/test";

test("market drafts, world map and dictionary open without a model", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveTitle(/(만들기|Create) — (트렌드 통역|Trend Interpreter)/);   // 화면마다 제목이 다르다(10-04)
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(/시장마다|For each market/);   // 첫 화면은 만들기(Plan 20)
  await expect(page.getByRole("navigation", { name: /^(주 메뉴|Main menu)$/ })).toBeVisible();

  await page.goto("/map");
  await expect(page.getByRole("main")).toBeVisible();
  await page.goto("/dictionary");
  await expect(page).toHaveURL(/\/dictionary$/);
  await expect(page.getByRole("main")).toBeVisible();
});

test("explore switches market and opens an entry", async ({ page }) => {
  await page.goto("/trends");                                                     // 둘러보기(예전 대시보드)

  // 일본을 고르면 일본에서 쓰이는 것만 남는다: 推し活 은 있고, 한국에서만 쓰는 자만추 는 빠진다
  await page.getByRole("navigation", { name: /^(시장|Markets)$/ }).getByRole("link", { name: /^(일본|Japan)/ }).click();
  await expect(page).toHaveURL(/m=JP/);
  await expect(page.getByRole("button", { name: /推し活/ })).toHaveCount(1);
  await expect(page.getByRole("button", { name: /자만추/ })).toHaveCount(0);

  await page.getByRole("button", { name: /推し活/ }).click();
  await page.getByRole("link", { name: /^(자세히 보기|Open entry)/ }).first().click();
  await expect(page).toHaveURL(/\/dictionary\/t_oshikatsu\?m=JP$/);   // 고른 시장을 사전 항목에 넘긴다
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("推し活");
});

test("recommend suggests memes for a product without a model", async ({ page }) => {
  await page.goto("/recommend");
  await page.getByLabel(/홍보 문구|Your copy/).fill("여름 한정 아이스 라떼");
  await page.getByRole("button", { name: /밈 추천받기|Suggest memes/ }).click();

  await expect(page.getByRole("heading", { name: /추천 밈|suggested memes/i })).toBeVisible();
  await expect(page.getByText(/예시 제품|sample product/)).toBeVisible();          // 모델 없는 환경임을 숨기지 않는다
  const items = page.getByRole("row");
  await expect(items.filter({ hasText: "원영적 사고" })).toHaveCount(1);
  await expect(items.filter({ hasText: "aura farming" })).toHaveCount(0);        // 친근한 톤에는 비꼬는 말투를 넣지 않는다

  // 사전은 새 탭으로 연다 — 추천 결과가 남아 있어야 한다
  const [tab] = await Promise.all([
    page.waitForEvent("popup"),
    items.filter({ hasText: "원영적 사고" }).getByRole("link", { name: /^원영적 사고/ }).click(),
  ]);
  await expect(tab).toHaveURL(/\/dictionary\/t_wonyoung\?from=recommend$/);
  await expect(page.getByRole("heading", { name: /추천 밈|suggested memes/i })).toBeVisible();
});

test("drafts copy and a script from a recommended meme without a model", async ({ page }) => {
  await page.goto("/recommend");
  await page.getByLabel(/홍보 문구|Your copy/).fill("여름 한정 아이스 라떼");
  await page.getByRole("button", { name: /밈 추천받기|Suggest memes/ }).click();
  const item = page.getByRole("row").filter({ hasText: "원영적 사고" });
  await item.getByRole("checkbox", { name: /원영적 사고 고르기|Pick 원영적 사고/ }).check();
  await page.getByRole("button", { name: /카피·대본 만들기|Draft copy and script/ }).click();

  await expect(page.getByRole("heading", { name: /만든 결과물|Drafts/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: /만든 결과물|Drafts/ })).toBeFocused();       // 결과가 오면 그 제목으로 초점을 옮긴다
  await expect(page.getByText(/AI가 만든 초안|AI-generated drafts/)).toBeVisible();      // 게시 전 확인 안내
  await expect(page.getByRole("tab", { name: /숏폼 대본|Short-form script/ })).toBeVisible();
  // 복사 버튼마다 무엇을 복사하는지 이름이 있다 — 썸네일 구성안에도 있다
  await expect(page.getByRole("button", { name: /^(복사|Copy): (인스타그램|Instagram) 1$/ })).toBeVisible();
  await page.getByRole("tab", { name: /썸네일 구성안|Thumbnail plan/ }).click();
  await expect(page.getByRole("button", { name: /^(복사|Copy): (썸네일 구성안|Thumbnail plan)$/ })).toBeVisible();
});
