import { test, expect } from "@playwright/test";
import { loadBriefing, SUMMARY_WAIT_MS } from "../lib/briefing-fetch";

test("summary request that answers is used as is", async () => {
  const calls: boolean[] = [];
  const res = await loadBriefing(async (summary) => (calls.push(summary), new Response("{}", { status: 200 })));
  expect(res.ok).toBe(true);
  expect(calls).toEqual([true]);
});

test("slow or failing summary falls back to the lists without the model", async () => {
  for (const first of [() => Promise.reject(new DOMException("timed out", "TimeoutError")), () => Promise.resolve(new Response("", { status: 503 }))]) {
    const calls: Array<[boolean, number]> = [];
    const res = await loadBriefing(async (summary, waitMs) => {
      calls.push([summary, waitMs]);
      return summary ? first() : new Response("{}", { status: 200 });
    });
    expect(res.ok).toBe(true);
    expect(calls[0]).toEqual([true, SUMMARY_WAIT_MS]);
    expect(calls[1][0]).toBe(false);
  }
});

test("when the lists also fail the caller sees the failure", async () => {
  const res = await loadBriefing(async (summary) => (summary ? Promise.reject(new Error("down")) : new Response("", { status: 500 })));
  expect(res.status).toBe(500);
});
