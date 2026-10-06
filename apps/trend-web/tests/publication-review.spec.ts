import { test, expect } from "@playwright/test";
import { batchDecision } from "../lib/publication-review";
import { createBatchDecisionHandler } from "../lib/publication-decision-handler";

test("batch decisions carry the seen hash and strip spoofed identities", () => {
  expect(batchDecision({ payload_sha256: "a".repeat(64), decision: "approve", by: "someone-else", publish: true })).toEqual({
    payload_sha256: "a".repeat(64), decision: "approve", allow_gate_exceptions: false,
  });
  expect(batchDecision({ payload_sha256: "b".repeat(64), decision: "reject", allow_gate_exceptions: true })?.allow_gate_exceptions).toBe(true);
});

test("malformed approval and implicit exceptions fail closed", () => {
  for (const raw of [null, [], {}, { payload_sha256: "short", decision: "approve" },
    { payload_sha256: "a".repeat(64), decision: "publish" },
    { payload_sha256: "a".repeat(64), decision: "approve", allow_gate_exceptions: "true" }]) {
    expect(batchDecision(raw)).toBeNull();
  }
});

const context = { params: Promise.resolve({ batchId: "batch-one" }) };
const request = (origin = "https://trend.test") => new Request("https://trend.test/api/publications/batch-one", {
  method: "POST", headers: { origin, "content-type": "application/json" },
  body: JSON.stringify({ payload_sha256: "a".repeat(64), decision: "approve", by: "spoofed" }),
});

test("approval refuses anonymous, ordinary, cross-site and missing-token requests before calling API", async () => {
  let calls = 0;
  const fetcher = async () => { calls++; return Response.json({}); };
  const reviewer = { user: "actual-reviewer", reviewer: true };
  for (const [account, token, origin, status] of [
    [null, "token", "https://trend.test", 401],
    [{ user: "reader", reviewer: false }, "token", "https://trend.test", 403],
    [reviewer, "token", "https://other.test", 403],
    [reviewer, undefined, "https://trend.test", 503],
  ] as const) {
    const handler = createBatchDecisionHandler(async () => account, () => token, fetcher);
    const response = await handler(request(origin), context);
    expect(response.status).toBe(status);
    expect(response.headers.get("cache-control")).toBe("private, no-store");
  }
  expect(calls).toBe(0);
});

test("approval uses the signed identity, seen hash and private server token", async () => {
  const handler = createBatchDecisionHandler(async () => ({ user: "actual-reviewer", reviewer: true }), () => "private-token",
    async (path, init) => {
      expect(path).toBe("/review/batches/batch-one/decision");
      expect(init.cache).toBe("no-store");
      expect(new Headers(init.headers).get("x-frontend-token")).toBe("private-token");
      expect(JSON.parse(init.body as string)).toEqual({ payload_sha256: "a".repeat(64), decision: "approve",
        by: "actual-reviewer", allow_gate_exceptions: false });
      return Response.json({ status: "approved" });
    });
  const response = await handler(request(), context);
  expect(response.status).toBe(200);
  expect(await response.json()).toEqual({ status: "approved" });
});

test("same-origin approval works behind the production proxy's internal request URL", async () => {
  let calls = 0;
  const handler = createBatchDecisionHandler(async () => ({ user: "reviewer", reviewer: true }), () => "token",
    async () => { calls++; return Response.json({ status: "approved" }); });
  const response = await handler(new Request("http://0.0.0.0:8080/api/publications/batch-one", {
    method: "POST", headers: { origin: "https://trend.example", host: "trend.example" },
    body: JSON.stringify({ payload_sha256: "a".repeat(64), decision: "approve" }),
  }), context);
  expect(response.status).toBe(200);
  expect(calls).toBe(1);
});
