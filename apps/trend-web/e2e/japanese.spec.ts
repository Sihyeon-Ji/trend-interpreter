import { expect, test } from "@playwright/test";

/* 일본어 화면(계획서 ktwoo-copy-flow-and-japanese-ui B) — 예시 모드. 첫 화면에서 日本語 를 고르면 문서 언어가 ja 가 되고
   초안·둘러보기·사전 항목이 일본어로 나온다. 일본어 뜻이 있는 말은 일본어로, 없는 말은 원문과 '翻訳なし' 안내. */

test("switching to 日本語 turns the start, drafts, explore and an entry into Japanese", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("group", { name: /^(화면 언어|Language)$/ }).getByRole("button", { name: "日本語" }).click();
  await expect(page.locator("html")).toHaveAttribute("lang", "ja");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(/市場ごと/);
  await expect(page.getByRole("navigation", { name: "メインメニュー" })).toBeVisible();
  await expect(page.getByRole("button", { name: "日本語", pressed: true })).toBeVisible();

  // 초안 — 시장마다 규칙이 고르고 AI가 쓰고 규칙이 다시 보고 사람이 승인한다(로그인하지 않으면 승인 대신 로그인 안내)
  await page.getByRole("textbox", { name: "商品" }).fill("夏限定のアイス黒糖ラテ");
  await page.getByRole("button", { name: "下書きを作る" }).click();
  await expect(page).toHaveURL(/\/drafts$/);
  const kr = page.getByRole("article", { name: "韓国" });
  await expect(kr.getByRole("list", { name: "韓国, 下書きができるまでの流れ" })).toBeVisible();
  await expect(kr.getByRole("heading", { name: /除外した言葉$/ })).toBeVisible();
  await expect(kr.getByText("ログインするとレビューを依頼できます。")).toBeVisible({ timeout: 30_000 });
  await expect(kr.getByRole("button", { name: "韓国の下書きを承認する" })).toHaveCount(0);

  // 둘러보기 → 사전 항목: 일본어 뜻이 있는 말
  await page.goto("/trends?m=JP");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("日本で今使われている言葉");
  await page.getByRole("button", { name: /推し活/ }).click();
  await page.getByRole("link", { name: /^詳しく見る/ }).first().click();
  await expect(page).toHaveURL(/\/dictionary\/t_oshikatsu\?m=JP$/);
  await expect(page.getByText("使えますか？")).toBeVisible();
  await expect(page.getByText(/^好きなアイドルやキャラクター（推し）を応援する活動全般/)).toBeVisible();
  await expect(page.locator("[data-untranslated]")).toHaveCount(0);

  // 일본어 뜻이 없는 말은 원문 뜻과 '翻訳なし' 안내
  await page.goto("/dictionary/t_jamanchu");
  await expect(page.locator("[data-untranslated]")).toHaveText(/^翻訳なし/);
  await expect(page.getByText(/^자연스러운 만남을 추구한다는 뜻/).first()).toBeVisible();
});
