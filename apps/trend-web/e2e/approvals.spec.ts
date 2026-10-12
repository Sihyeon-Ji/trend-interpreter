import { expect, test, type Page } from "@playwright/test";
import { secret, sessionCookie } from "./session";

/* 문구 승인 기록(Plan 20 ⑤)과 모든 문구 다시 검사(④) — 예시 모드. 권한은 실제 모드와 같게 검사하고, 기록은 서버에 남기지 않는다(sample).
   승인은 검수자만(읽기 전용은 보기만), 검수 요청은 로그인한 계정만, 익명은 로그인 안내만. 관리 화면은 규칙으로 나눈 세 묶음과 지난 기록. */

async function draft(page: Page) {
  await page.goto("/");
  await page.getByRole("textbox", { name: /^(제품|Product)$/ }).fill("여름 한정 아이스 흑당 라떼");
  await page.getByRole("button", { name: /^(초안 만들기|Create drafts)$/ }).click();
  await expect(page).toHaveURL(/\/drafts$/);
  const kr = page.getByRole("article", { name: /^(한국|Korea)$/ });
  // 문구 넷을 모두 규칙으로 다시 본다 — 첫 문구만 보던 것(Plan 20 ④)
  await expect(kr.locator(".rs-copy")).toHaveCount(4, { timeout: 30_000 });
  await expect(kr.locator(".rs-copy .rs-check[data-state='ok'], .rs-copy .rs-check[data-state='flag']")).toHaveCount(4, { timeout: 30_000 });
  return kr;
}

const sign = async (page: Page, baseURL: string | undefined, user: string, reviewer: boolean, readOnly = false) =>
  page.context().addCookies([{ name: "admin_session", value: sessionCookie(user, reviewer, readOnly), url: baseURL ?? "http://localhost:3000" }]);

const body = { market: "KR", term_id: "t_wonyoung", product: "라떼", copies: [{ platform: "instagram", text: "원영적 사고 라떼", hashtags: [] }], fit: "ok", fit_copy: 0 };

test("anonymous visitors cannot store copy: the route refuses before anything is kept", async ({ page, baseURL }) => {
  const res = await page.request.post("/api/approvals", { data: body, headers: { origin: baseURL ?? "http://localhost:3000" } });
  expect(res.status()).toBe(401);
  expect((await page.request.post("/api/approvals/ap_0123456789abcdef", { data: { decision: "approve" } })).status()).toBe(401);
});

test.describe("signed in", () => {
  test.skip(!secret, "PLAYWRIGHT_SESSION_SECRET 이 없으면 서명된 계정을 만들 수 없다");

  test("an ordinary account sends a review request and sees it waiting, and cannot approve", async ({ page, baseURL }) => {
    await sign(page, baseURL, "reader", false);
    const kr = await draft(page);
    await expect(kr.getByRole("button", { name: /초안 승인|Approve the/ })).toHaveCount(0);
    await kr.getByRole("button", { name: /한국 검수 요청|Request review for Korea/ }).click();
    await expect(kr.getByRole("status").filter({ hasText: /검수를 기다려요|Waiting for review/ })).toBeVisible();
    await expect(kr.getByText(/예시 화면이라 기록을 서버에 남기지 않아요|nothing is recorded on the server/)).toBeVisible();
    await expect(kr.getByRole("button", { name: /이 문구 복사|Copy this line/ })).toHaveCount(0);       // 승인되기 전에는 복사가 열리지 않는다
    const res = await page.request.post("/api/approvals", { data: { ...body, decision: "approve" }, headers: { origin: baseURL ?? "http://localhost:3000" } });
    expect(res.status()).toBe(403);
  });

  test("a reviewer approves on the draft in one step and copying opens", async ({ page, baseURL }) => {
    await sign(page, baseURL, "e2e", true);
    const kr = await draft(page);
    await kr.getByRole("button", { name: /한국 초안 승인|Approve the Korea draft/ }).click();
    await expect(kr.getByText(/e2e 승인|Approved by e2e/).first()).toBeVisible();
    await expect(kr.getByRole("button", { name: /문구 모두 복사|Copy all lines/ })).toBeVisible();
    await expect(kr.getByRole("button", { name: /이 문구 복사|Copy this line/ })).toHaveCount(4);
    await expect(page.getByText(/\d개 시장 중 1곳 승인|1 of \d markets approved/).first()).toBeVisible();
  });

  test("a read-only judge account sees the draft but cannot approve or ask, and the route refuses", async ({ page, baseURL }) => {
    await sign(page, baseURL, "judge", true, true);
    const kr = await draft(page);
    await expect(kr.getByText(/읽기 전용 계정이라 승인하거나|Read-only accounts can't approve/)).toBeVisible();
    await expect(kr.getByRole("button", { name: /초안 승인|검수 요청|Approve the|Request review/ })).toHaveCount(0);
    const res = await page.request.post("/api/approvals", { data: body, headers: { origin: baseURL ?? "http://localhost:3000" } });
    expect(res.status()).toBe(403);
  });

  test("a line with a word the rules forbid blocks approval and suggests writing again", async ({ page, baseURL }) => {
    await sign(page, baseURL, "e2e", true);
    // 다시 검사의 결과만 바꿔 둔다: 둘째 문구에 '사용 자제' 말이 들었다
    await page.route("**/api/copy-check/all", async (route) => {
      const res = await route.fetch();
      const json = await res.json();
      json.items[1].memes = [{ ...json.items[0].memes[0], term_id: "t_jungti", canonical: "중티", matched: "중티", issues: [{ code: "avoid", note: "" }] }];
      await route.fulfill({ response: res, json });
    });
    const kr = await draft(page);
    const approve = kr.getByRole("button", { name: /한국 초안 승인|Approve the Korea draft/ });
    await expect(approve).toBeDisabled();
    await expect(kr.getByText(/쓰지 말라고 한 말이 든 문구가 있어 승인할 수 없어요|can't be approved/)).toBeVisible();
    await expect(kr.getByText(/Instagram 2/).last()).toBeVisible();
    await expect(kr.getByRole("button", { name: /^(다시 쓰기|Write again)$/ })).toBeEnabled();
  });

  test("an image meme carries a rights note", async ({ page, baseURL }) => {
    await sign(page, baseURL, "reader", false);
    await page.route("**/api/generate", async (route) => {
      const res = await route.fetch();
      const json = await res.json();
      await route.fulfill({ response: res, json: { ...json, image_memes: ["t_wonyoung"] } });
    });
    const kr = await draft(page);
    await expect(kr.getByText(/그림을 쓰려면 권리를 먼저 확인하세요|Check the rights before you use the image/)).toBeVisible();
  });
});

test.describe("admin copy approvals", () => {
  test.skip(!secret, "PLAYWRIGHT_SESSION_SECRET 이 없으면 관리 화면을 열 수 없다");

  test("waiting requests sit in three rule groups, 'read first' opens first, blocked ones cannot be approved", async ({ page, baseURL }) => {
    await sign(page, baseURL, "e2e", true);
    await page.goto("/admin/approvals");
    await expect(page).toHaveTitle(/문구 승인|Copy approvals/);
    await expect(page.getByRole("link", { name: /^(문구 승인|Copy approvals)$/ })).toHaveAttribute("aria-current", "page");
    const group = (g: string) => page.locator(`details[data-group='${g}']`);
    await expect(group("blocked").locator("summary")).toContainText(/막힘\s*1|Blocked\s*1/);
    await expect(group("read").locator("summary")).toContainText(/읽어 볼 것\s*2|Read first\s*2/);
    await expect(group("clean").locator("summary")).toContainText(/깨끗함\s*1|Clear\s*1/);
    await expect(group("read")).toHaveAttribute("open", "");
    await expect(group("blocked")).not.toHaveAttribute("open", "");
    // 읽어 볼 것은 최신순 — 30분 전(AI 의견 '뜻과 다름') 요청이 먼저
    await expect(group("read").getByRole("listitem").first()).toContainText(/뜻과 다르게 쓴 것 같다고 봤어요|thinks a word is used differently/);
    await group("blocked").locator("summary").click();
    const blocked = group("blocked").getByRole("listitem").first();
    await expect(blocked.getByRole("button", { name: /승인$|^Approve/ })).toBeDisabled();
    await expect(blocked.getByText(/막힌 문구가 있어 승인할 수 없어요|A line is blocked/)).toBeVisible();
    await expect(blocked.getByText(/쓰지 말라고 정한 말|a word the rules say not to use/).first()).toBeVisible();
    // 읽어 보고 승인하면 지난 기록으로 옮겨 간다
    const first = group("read").getByRole("listitem").first();
    await first.getByRole("textbox", { name: /메모|Note/ }).fill("읽어 봤어요");
    await first.getByRole("button", { name: /승인$|^Approve/ }).click();
    await expect(group("read").locator("summary")).toContainText(/읽어 볼 것\s*1|Read first\s*1/);
    const past = page.getByRole("region", { name: /지난 기록|Past decisions/ });
    await expect(past.getByRole("listitem").first()).toContainText(/e2e 승인|Approved by e2e/);
    await expect(past.getByRole("listitem").first()).toContainText("읽어 봤어요");
    await expect(past.getByText(/보존 기간\(30일\)이 지나 본문을 지웠어요|deleted after the 30-day/)).toBeVisible();
  });

  test("a read-only judge account reads the queue but every decision is refused", async ({ page, baseURL }) => {
    await sign(page, baseURL, "judge", true, true);
    await page.goto("/admin/approvals");
    await expect(page.getByRole("note")).toContainText(/읽기 전용 계정|Read-only account/);
    const read = page.locator("details[data-group='read']");
    await expect(read.getByRole("listitem").first().getByRole("button", { name: /승인$|^Approve/ })).toBeDisabled();
    await expect(read.getByRole("listitem").first().getByRole("button", { name: /반려$|^Reject/ })).toBeDisabled();
    const res = await page.request.post("/api/approvals/sample-read-1", { data: { decision: "approve" }, headers: { origin: baseURL ?? "http://localhost:3000" } });
    expect(res.status()).toBe(403);
  });

  test("ordinary and anonymous accounts cannot open the queue", async ({ page, baseURL }) => {
    await page.goto("/admin/approvals");
    await expect(page).toHaveURL(/\/login/);
    await sign(page, baseURL, "reader", false);
    await page.goto("/admin/approvals");
    await expect(page).toHaveURL(/\/me(?:\?|$)/);
    await expect(page.getByRole("alert").filter({ hasText: /관리 권한이 있는 계정만|only for accounts with admin access/ })).toBeVisible();
    const res = await page.request.post("/api/approvals/sample-read-1", { data: { decision: "approve" }, headers: { origin: baseURL ?? "http://localhost:3000" } });
    expect(res.status()).toBe(403);
  });
});
