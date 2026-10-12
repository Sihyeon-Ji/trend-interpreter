import { expect, test } from "@playwright/test";
import { approvalDecision, approvalRequest, copyIssues, fullText, groupOf } from "../lib/approval";
import { createApprovalHandlers } from "../lib/approval-handler";
import type { CopyCheck } from "../lib/types";

/* 문구 승인 기록(Plan 20 ⑤) — 브라우저·서버 없이. 묶음 규칙은 백엔드 storage/approvals.group 과 같고(test_copy_approvals.py 와 같은 사례),
   라우트는 익명·읽기 전용·검수자가 아닌 승인·다른 사이트를 백엔드 전에 막고, 이름은 세션에서만 넣는다. */

const check = (codes: string[], unsafe = false): CopyCheck => ({
  region: "KR", unsafe, x_length: 10, fit_source: "none",
  memes: [{ term_id: "t", canonical: "t", lang: "ko", matched: "t", gloss_ko: "", gloss_en: "", regions: ["KR"], lifecycle: "steady",
    issues: codes.map((code) => ({ code: code as CopyCheck["memes"][number]["issues"][number]["code"], note: "" })) }],
});

test("groups follow the backend rules: blocking codes first, then flags, then the AI's view", () => {
  expect(groupOf([[], ["fading"]], "ok")).toEqual({ group: "read", reasons: ["fading"] });
  expect(groupOf([["no_script"], ["unsafe"]], "off")).toEqual({ group: "blocked", reasons: ["unsafe", "no_script", "fit_off"] });
  expect(groupOf([[]], "ok")).toEqual({ group: "clean", reasons: [] });
  expect(groupOf([[]], null)).toEqual({ group: "read", reasons: ["fit_none"] });
  expect(copyIssues(check(["fading", "avoid", "fading"], true))).toEqual(["avoid", "unsafe", "fading"]);
  expect(copyIssues(check(["crude", "sensitive"]))).toEqual(["crude", "sensitive"]);
  expect(fullText({ text: "본문", hashtags: ["여름", "라떼"] })).toBe("본문\n\n#여름 #라떼");
});

const copy = { platform: "instagram", text: " 럭키비키 라떼 ", hashtags: ["여름", " ", "x".repeat(80)] };

test("the request body keeps known fields only and never the requester, the group or check results", () => {
  const got = approvalRequest({ market: "kr", term_id: "t_lucky", product: "라떼", copies: [copy], fit: "ok", fit_note: "맞아요", fit_copy: 0,
    by: "someone-else", group: "clean", issues: [[]], decision: "approve" });
  expect(got).toEqual({ market: "KR", term_id: "t_lucky", product: "라떼", copies: [{ platform: "instagram", text: "럭키비키 라떼", hashtags: ["여름", "x".repeat(60)] }],
    fit: "ok", fit_note: "맞아요", fit_copy: 0, decision: "approve" });
  expect(approvalRequest({ market: "KR", term_id: "t", copies: [copy], fit: "ok", fit_copy: 3 })?.fit).toBeNull();   // 없는 문구의 의견은 버린다
  for (const bad of [null, [], { market: "US", term_id: "t", copies: [copy] }, { market: "KR", term_id: "bad id", copies: [copy] },
    { market: "KR", term_id: "t", copies: [] }, { market: "KR", term_id: "t", copies: Array(7).fill(copy) },
    { market: "KR", term_id: "t", copies: [{ ...copy, platform: "tiktok" }] }, { market: "KR", term_id: "t", copies: [{ ...copy, text: "" }] },
    { market: "KR", term_id: "t", copies: [copy], decision: "reject" }]) {
    expect(approvalRequest(bad), JSON.stringify(bad)).toBeNull();
  }
  expect(approvalDecision({ decision: "reject", memo: " 다시 ", by: "x" })).toEqual({ decision: "reject", memo: "다시" });
  expect(approvalDecision({ decision: "publish" })).toBeNull();
});

const ctx = { params: Promise.resolve({ id: "ap_0123456789abcdef" }) };
const post = (body: unknown, origin = "https://trend.test") => new Request("https://trend.test/api/approvals", {
  method: "POST", headers: { origin, "content-type": "application/json" }, body: JSON.stringify(body),
});
const ask = { market: "KR", term_id: "t_lucky", product: "라떼", copies: [copy], fit: "ok", fit_copy: 0 };
const reviewer = { user: "rev", reviewer: true };
const handlers = (account: { user: string; reviewer: boolean; readOnly?: boolean } | null, opts: { token?: string; sample?: boolean; fetcher?: (p: string, i: RequestInit) => Promise<Response> } = {}) =>
  createApprovalHandlers({
    viewer: async () => account, token: () => ("token" in opts ? opts.token : "private-token"), sample: !!opts.sample,
    fetcher: opts.fetcher ?? (async () => Response.json({})), sampleCheck: (text) => check(text.includes("자제말") ? ["avoid"] : []),
  });

test("requests refuse anonymous and read-only accounts, approvals need a reviewer, and nothing reaches the API before that", async () => {
  let calls = 0;
  const fetcher = async () => { calls++; return Response.json({}); };
  for (const [account, body, origin, status, error] of [
    [null, ask, "https://trend.test", 401, "signed_out"],                                        // 익명 문구는 서버에 쌓지 않는다
    [{ user: "judge", reviewer: true, readOnly: true }, ask, "https://trend.test", 403, "readonly"],
    [{ user: "mk", reviewer: false }, { ...ask, decision: "approve" }, "https://trend.test", 403, "reviewer_required"],
    [reviewer, ask, "https://other.test", 403, "same_origin_required"],
    [reviewer, { ...ask, market: "US" }, "https://trend.test", 400, "bad_request"],
  ] as const) {
    const res = await handlers(account, { fetcher }).create(post(body, origin));
    expect(res.status).toBe(status);
    expect((await res.json()).error).toBe(error);
    expect(res.headers.get("cache-control")).toBe("private, no-store");
  }
  expect((await handlers(reviewer, { token: undefined, fetcher }).create(post(ask))).status).toBe(503);
  expect(calls).toBe(0);
});

test("requests go to the API with the signed account name and the private token", async () => {
  const res = await handlers({ user: "mk", reviewer: false }, {
    fetcher: async (path, init) => {
      expect(path).toBe("/approvals");
      expect(new Headers(init.headers).get("x-frontend-token")).toBe("private-token");
      expect(JSON.parse(init.body as string)).toEqual({ ...approvalRequest(ask), by: "mk" });
      return Response.json({ approval_id: "ap_1", status: "pending" });
    },
  }).create(post({ ...ask, by: "spoofed" }));
  expect(res.status).toBe(200);
  expect(await res.json()).toEqual({ approval_id: "ap_1", status: "pending" });
  const blocked = await handlers(reviewer, { fetcher: async () => Response.json({ detail: "blocked", reasons: ["avoid"] }, { status: 409 }) }).create(post(ask));
  expect(blocked.status).toBe(409);
  expect(await blocked.json()).toEqual({ error: "blocked", reasons: ["avoid"] });
});

test("sample mode checks the same permissions and rules but records nothing", async () => {
  let calls = 0;
  const fetcher = async () => { calls++; return Response.json({}); };
  const pending = await (await handlers({ user: "mk", reviewer: false }, { sample: true, fetcher }).create(post(ask))).json();
  expect(pending).toMatchObject({ status: "pending", group: "clean", requested_by: "mk", sample: true });
  const approved = await (await handlers(reviewer, { sample: true, fetcher }).create(post({ ...ask, decision: "approve" }))).json();
  expect(approved).toMatchObject({ status: "approved", decided_by: "rev", sample: true });
  const blocked = await handlers(reviewer, { sample: true, fetcher }).create(post({ ...ask, copies: [{ ...copy, text: "자제말 라떼" }], decision: "approve" }));
  expect(blocked.status).toBe(409);
  expect((await handlers(null, { sample: true, fetcher }).create(post(ask))).status).toBe(401);
  expect(calls).toBe(0);
});

test("decisions are for reviewers only, read-only accounts are refused, and the decider comes from the session", async () => {
  const decision = (origin?: string) => new Request("https://trend.test/api/approvals/ap_0123456789abcdef", {
    method: "POST", headers: { origin: origin ?? "https://trend.test" }, body: JSON.stringify({ decision: "approve", memo: "좋아요", by: "spoofed" }),
  });
  for (const [account, origin, status] of [
    [null, undefined, 401], [{ user: "mk", reviewer: false }, undefined, 403], [{ user: "judge", reviewer: true, readOnly: true }, undefined, 403],
    [reviewer, "https://other.test", 403],
  ] as const) {
    expect((await handlers(account, { fetcher: async () => { throw new Error("must not call"); } }).decide(decision(origin), ctx)).status).toBe(status);
  }
  const res = await handlers(reviewer, {
    fetcher: async (path, init) => {
      expect(path).toBe("/review/approvals/ap_0123456789abcdef/decision");
      expect(JSON.parse(init.body as string)).toEqual({ decision: "approve", memo: "좋아요", by: "rev" });
      return Response.json({ status: "approved" });
    },
  }).decide(decision(), ctx);
  expect(await res.json()).toEqual({ status: "approved" });
});

test("the requester reads the state through the server with their own name", async () => {
  expect((await handlers(null).state(new Request("https://trend.test/x"), ctx)).status).toBe(401);
  expect((await handlers({ user: "mk", reviewer: false }, { sample: true }).state(new Request("https://trend.test/x"), ctx)).status).toBe(404);
  const res = await handlers({ user: "mk", reviewer: false }, {
    fetcher: async (path) => { expect(path).toBe("/approvals/ap_0123456789abcdef?viewer=mk"); return Response.json({ status: "approved" }); },
  }).state(new Request("https://trend.test/x"), ctx);
  expect(await res.json()).toEqual({ status: "approved" });
});
