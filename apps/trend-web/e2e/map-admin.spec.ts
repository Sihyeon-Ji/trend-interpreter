import { createHmac } from "node:crypto";
import { expect, test } from "@playwright/test";

/* 세계 지도·관리 화면 개편(2026-09-29) — 예시 모드에서 모델·서버 없이. */

test("world map picks regions and opens them on the dashboard", async ({ page }) => {
  await page.goto("/map?regions=KR&list=fading");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(/세계 지도|World map/);
  const table = page.getByRole("table");
  // 목표 지역 10곳과 전 세계 — 110m 지도에 도형이 없는 홍콩·싱가포르도 있다
  await expect(table.getByRole("checkbox")).toHaveCount(11);
  await expect(table.getByRole("checkbox", { name: /한국 고르기|Pick South Korea|Pick Korea/ })).toBeChecked();
  await table.getByRole("checkbox", { name: /홍콩 고르기|Pick Hong Kong/ }).check();
  await expect(page).toHaveURL(/regions=KR%2CHK|regions=KR,HK/);
  const open = page.getByRole("link", { name: /대시보드에서 보기|View on dashboard/ }).first();
  await expect(open).toHaveAttribute("href", /\/\?regions=KR(%2C|,)HK&list=fading/);   // 들어올 때 보던 목록을 그대로 넘긴다
  await open.click();
  await expect(page).toHaveURL(/regions=KR(%2C|,)HK/);
});

test("world map lists memes across borders and shows how they differ", async ({ page }) => {
  await page.goto("/map?tab=topics");
  await page.getByRole("button", { name: "오징어 게임" }).click();
  await expect(page).toHaveURL(/topic=/);
  await expect(page.getByRole("heading", { name: /오징어 게임 나라별 차이/ })).toBeVisible();
  await expect(page.getByRole("button", { name: "오징어 게임" })).toHaveAttribute("aria-current", "true");
});

test("world map does not scroll sideways on a phone", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  for (const path of ["/map", "/map?tab=topics"]) {
    await page.goto(path);
    const [scroll, client] = await page.evaluate(() => [document.documentElement.scrollWidth, document.documentElement.clientWidth]);
    expect(scroll).toBeLessThanOrEqual(client);
  }
});

/* 관리 화면은 검수자 세션이 있어야 열린다. 개발 서버와 같은 SESSION_SECRET 을 PLAYWRIGHT_SESSION_SECRET 으로 주면 돈다. */
const secret = process.env.PLAYWRIGHT_SESSION_SECRET;
const b64 = (b: Buffer | string) => Buffer.from(b).toString("base64").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
function reviewerCookie(s: string) {
  const payload = b64(JSON.stringify({ u: "e2e", r: true, exp: Math.floor(Date.now() / 1000) + 3600 }));
  return `${payload}.${b64(createHmac("sha256", s).update(payload).digest())}`;
}

test.describe("admin", () => {
  test.skip(!secret, "PLAYWRIGHT_SESSION_SECRET 이 없으면 관리 화면을 열 수 없다");
  test.beforeEach(async ({ context, baseURL }) => {
    await context.addCookies([{ name: "admin_session", value: reviewerCookie(secret!), url: baseURL ?? "http://localhost:3000" }]);
  });

  test("review shows evidence before a decision and the decision can be undone", async ({ page }) => {
    await page.goto("/admin");
    await expect(page.getByText(/결정은 e2e 이름으로 기록됩니다|Decisions are recorded as e2e/)).toBeVisible();
    await expect(page.getByRole("button", { name: /승인$|^Approve/ })).toHaveCount(0);         // 펼치기 전에는 결정 단추가 없다
    await page.getByRole("button", { name: /6-7 검토|Review 6-7/ }).click();
    const detail = page.getByRole("region", { name: "6-7" });
    await expect(detail.getByText(/지금 실린 뜻|Published meaning/)).toBeVisible();
    await expect(detail.getByRole("link", { name: /원문 보기|Open source/ }).first()).toBeVisible();
    await detail.getByRole("button", { name: /6-7 승인|Approve 6-7/ }).click();
    const undo = page.getByRole("button", { name: /되돌리기|Undo/ });
    await expect(undo).toBeFocused();
    await undo.click();
    await expect(page.getByRole("button", { name: /6-7 검토|Review 6-7/ })).toBeFocused();
  });

  test("a proposed fix sits beside the published meaning and is published as a new version", async ({ page }) => {
    await page.goto("/admin?kind=correction");                                                   // 문서 대조의 제안(Plan 12) — 예시에 종류마다 하나
    await expect(page.getByRole("link", { name: /^(고칠 안|Proposed fix) \d+$/ })).toHaveAttribute("aria-current", "page");
    await page.getByRole("button", { name: /aura farming 검토|Review aura farming/ }).click();
    const detail = page.getByRole("region", { name: "aura farming" });
    await expect(detail.getByRole("heading", { name: /^(지금 실린 뜻|Published meaning)$/ })).toBeVisible();   // 지금 뜻은 그대로 실린 채
    await expect(detail.getByRole("heading", { name: /^(고칠 안|Proposed fix)$/ })).toBeVisible();
    await expect(detail.getByRole("link", { name: /en\.wikipedia\.org\/wiki\/Aura_farming/ })).toBeVisible();   // 사유의 참고 문서
    await detail.getByRole("button", { name: /aura farming 고칠 안 싣기|Publish the fix aura farming/ }).click();
    const done = page.getByRole("listitem").filter({ has: page.getByRole("button", { name: /되돌리기|Undo/ }) });
    await expect(done).toContainText(/aura farming.*(새 판으로 실었습니다|Published the fix as a new version)/);
    await expect(done.getByRole("button", { name: /되돌리기|Undo/ })).toBeFocused();
  });

  test("status and risk tabs open with their own titles", async ({ page }) => {
    await page.goto("/admin/status");
    await expect(page).toHaveTitle(/수집 현황|Collection status/);
    await expect(page.getByRole("link", { name: /수집 현황|Collection status/ })).toHaveAttribute("aria-current", "page");
    await page.goto("/admin/risk?all=1");                                                   // 예전 주소는 '전체' 로
    await expect(page.getByRole("link", { name: /^(전체|All) \d+$/ })).toHaveAttribute("aria-current", "page");
  });
});
