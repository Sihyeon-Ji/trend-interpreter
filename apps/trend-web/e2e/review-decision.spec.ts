import { expect, test } from "@playwright/test";
import { reviewDecision } from "../lib/review-decision";

/* 검수 결정 라우트(app/api/review/[termId])가 백엔드로 넘기는 본문 — 브라우저·서버 없이 라우트가 쓰는 거르개를 본다.
   종류(kind)·제안의 표(token)·고른 문서(choice)는 그대로 넘기고, 결정한 사람(by)은 받지 않는다(라우트가 세션에서 넣는다). */

test("the review route forwards kind, token and a document-address choice as given", () => {
  const body = { decision: "approve", meaning_id: "m_1", kind: "conflict", token: "1d83be920103ab12", choice: "https://en.wikipedia.org/wiki/Skibidi_Toilet" };
  expect(reviewDecision(body)).toEqual({ ok: true, body });
  expect(reviewDecision({ decision: "approve", kind: "conflict", token: "t", choice: "keep", meaning_id: "m_1" })).toEqual({
    ok: true, body: { decision: "approve", meaning_id: "m_1", kind: "conflict", token: "t", choice: "keep" } });
  expect(reviewDecision({ decision: "reject" })).toEqual({ ok: true, body: { decision: "reject", meaning_id: null, kind: null, token: null, choice: null } });
  const spoofed = reviewDecision({ decision: "approve", by: "someone-else", kind: "correction", token: "t", meaning_id: "m" });
  expect(spoofed.ok && "by" in spoofed.body).toBe(false);                                   // 결정한 사람은 세션에서만
});

test("the review route refuses malformed decisions before they reach the backend", () => {
  const ok = { decision: "approve", meaning_id: "m_1", kind: "correction", token: "t" };
  for (const bad of [
    { ...ok, decision: "publish" },
    { ...ok, kind: "fix" },
    { ...ok, token: 12 },
    { ...ok, token: "x".repeat(65) },
    { ...ok, choice: 1 },                                                                    // 번호로는 고르지 않는다
    { ...ok, choice: "javascript:alert(1)" },
    { ...ok, meaning_id: 3 },
    null,
    ["approve"],
  ]) {
    expect(reviewDecision(bad).ok, JSON.stringify(bad)).toBe(false);
  }
});
