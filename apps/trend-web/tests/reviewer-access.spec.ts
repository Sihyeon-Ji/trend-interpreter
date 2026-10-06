import { expect, test } from "@playwright/test";
import { createReviewerReader, ReviewerAccessError } from "../lib/reviewer-access";
import { readSession, signSession } from "../lib/session";

const SECRET = "test-review-session-secret";

test("anonymous, ordinary, expired and tampered sessions never send a review request", async () => {
  const regular = await signSession("reader", false, SECRET);
  const reviewer = await signSession("reviewer", true, SECRET);
  const expired = await signSession("reviewer", true, SECRET, -1);
  for (const [cookie, status] of [[undefined, 401], [regular, 403], [expired, 401], [`${reviewer}tampered`, 401]] as const) {
    let calls = 0;
    const read = createReviewerReader(
      async () => { calls++; return new Response("[]"); },
      () => readSession(cookie, SECRET),
      () => "server-review-token",
    );
    await expect(read("/review/queue")).rejects.toMatchObject({ status });
    expect(calls).toBe(0);
  }
});

test("a verified reviewer read attaches the server token and disables shared caching", async () => {
  const cookie = await signSession("reviewer", true, SECRET);
  const calls: Array<{ path: string; token: string | null; cache: string | undefined }> = [];
  const read = createReviewerReader(
    async (path, init) => {
      calls.push({ path, token: new Headers(init.headers).get("x-frontend-token"), cache: init.cache });
      return new Response("[]");
    },
    () => readSession(cookie, SECRET),
    () => "server-review-token",
  );
  await read("/review/queue");
  expect(calls).toEqual([{ path: "/review/queue", token: "server-review-token", cache: "no-store" }]);
});

test("review authorization is checked for every request and missing configuration fails closed", async () => {
  let viewer: { user: string; reviewer: boolean } | null = { user: "reviewer", reviewer: true };
  let token: string | undefined = "server-review-token";
  let calls = 0;
  const read = createReviewerReader(
    async () => { calls++; return new Response("[]"); },
    async () => viewer,
    () => token,
  );
  await read("/review/stats");
  viewer = null;
  await expect(read("/review/stats")).rejects.toMatchObject({ status: 401 });
  viewer = { user: "reviewer", reviewer: true };
  token = undefined;
  await expect(read("/review/stats")).rejects.toBeInstanceOf(ReviewerAccessError);
  expect(calls).toBe(1);
});
