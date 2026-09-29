import { expect, test } from "@playwright/test";

/* 화면 개편 2차(메시지 해석·사전·로그인) — 예시 데이터로, 모델 없이. */

test("explain puts the input first, labels the sample and explains a pasted message", async ({ page }) => {
  await page.goto("/explain");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(/메시지 해석|Explain a message/);   // 메뉴와 같은 이름
  const input = page.getByLabel(/해석할 글 또는 질문|Text to explain/);
  const example = page.getByRole("heading", { name: /^(결과|Result)$/ });
  await expect(example).toBeVisible();
  // 입력 칸이 예시 결과보다 위에 있다
  const [ib, eb] = [await input.boundingBox(), await example.boundingBox()];
  expect(ib!.y).toBeLessThan(eb!.y);
  await expect(page.getByText(/^(예시|Sample)$/).first()).toBeVisible();

  // 빈 채로 누르면 요청하지 않고 할 일을 알린다
  await page.getByRole("button", { name: /^(해석하기|Explain)$/ }).click();
  await expect(page.getByText(/해석할 글이나 질문을 넣어 주세요|Enter some text/)).toBeVisible();

  await input.fill("오늘 팝업 줄 섰는데 마지막 한 자리 남아 있었음 완전 럭키비키잖아 원영적 사고 가자");
  await page.getByRole("button", { name: /^(해석하기|Explain)$/ }).click();
  const result = page.getByRole("heading", { name: /^(결과|Result)$/ });
  await expect(result).toBeFocused();                                              // 결과가 오면 결과 제목으로 초점을 옮긴다
  const row = page.getByRole("listitem").filter({ has: page.getByRole("heading", { level: 3, name: "럭키비키" }) });
  await expect(row.getByText(/^(단계|Stage)$/)).toBeVisible();
  await expect(row.getByText(/^(쓸 때 조심|Watch out)$/)).toBeVisible();
  await expect(input).toHaveValue("");                                             // 성공했을 때만 비운다
});

test("dictionary rows answer stage and risk, and the region filter follows the dashboard rule", async ({ page }) => {
  await page.goto("/dictionary?regions=JP");
  const table = page.getByRole("table");
  await expect(table.getByRole("columnheader", { name: /^(단계|Stage)$/ })).toBeVisible();
  await expect(table.getByRole("columnheader", { name: /^(쓸 때 조심|Watch out)$/ })).toBeVisible();
  await expect(table.getByRole("link", { name: "推し活" })).toHaveAttribute("lang", "ja");
  await expect(table.getByRole("link", { name: "자만추" })).toHaveCount(0);

  await page.getByRole("button", { name: /^(전체|All) \d+$/ }).click();
  await expect(table.getByRole("link", { name: "자만추" })).toHaveCount(1);
  await expect(page).toHaveURL(/\/dictionary$/);

  await page.getByLabel(/사전 검색|Search the dictionary/).fill("없는말없는말");
  await expect(page.getByText(/맞는 표현이 없습니다|No expressions match/)).toBeVisible();
  await expect(page).toHaveURL(/q=/);
});

test("login keeps next on the same site and explains empty fields", async ({ page }) => {
  await page.goto("/login?next=//evil.example");
  await expect(page.locator('input[name="next"]')).toHaveCount(0);                 // 다른 사이트로는 돌려보내지 않는다
  await page.getByRole("button", { name: /^(로그인|Sign in)$/ }).click();
  await expect(page.getByText(/아이디를 입력해 주세요|Enter your username/)).toBeVisible();
  await expect(page.getByLabel(/^(아이디|Username)$/)).toBeFocused();

  await page.goto("/login?next=/recommend");
  await expect(page.locator('input[name="next"]')).toHaveValue("/recommend");
});
