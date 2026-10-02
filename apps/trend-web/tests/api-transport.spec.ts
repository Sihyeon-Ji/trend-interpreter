import { test, expect } from "@playwright/test";
import { createApiTransport, type ApiRequestInit } from "../lib/api-transport";

const ORIGIN = "https://trend-api-example.a.run.app";
const token = (aud = ORIGIN, exp = Math.floor(Date.now() / 1000) + 3600) =>
  ["header", Buffer.from(JSON.stringify({ aud, exp })).toString("base64url"), "signature"].join(".");
const metadata = (value = token()) => new Response(value, { headers: { "Metadata-Flavor": "Google" } });

function mockFetch(identity: () => Promise<Response> = async () => metadata()) {
  const calls: Array<{ url: string; init?: ApiRequestInit }> = [];
  const fetcher = async (url: string, init?: ApiRequestInit) => {
    calls.push({ url, init });
    return url.startsWith("http://metadata.google.internal/") ? identity() : new Response("data: ready\n\n");
  };
  return { calls, fetcher };
}

test("local mode never requests an identity token and preserves request settings", async () => {
  const { calls, fetcher } = mockFetch();
  const request = createApiTransport("http://localhost:8080", "none", false, fetcher);
  await request("/terms?q=hello", { next: { revalidate: 60 }, headers: { "x-serverless-authorization": "untrusted" } });
  expect(calls).toHaveLength(1);
  expect(calls[0].init?.next).toEqual({ revalidate: 60 });
  expect(new Headers(calls[0].init?.headers).has("x-serverless-authorization")).toBe(false);
});

test("concurrent reads and writes share one refresh without sharing caller credentials", async () => {
  const value = token();
  const { calls, fetcher } = mockFetch(async () => metadata(value));
  const request = createApiTransport(ORIGIN, "google-id-token", true, fetcher);
  await Promise.all([
    request("/terms"),
    request("/review/id", { method: "POST", body: "decision", headers: { "x-frontend-token": "reviewer" } }),
  ]);
  await request("/prefs/me", { headers: { authorization: "Bearer user" } });
  expect(calls.filter((call) => call.url.includes("metadata.google.internal"))).toHaveLength(1);
  const first = calls[0];
  expect(new URL(first.url).searchParams.get("audience")).toBe(ORIGIN);
  expect(new Headers(first.init?.headers).get("Metadata-Flavor")).toBe("Google");
  expect(first.init?.cache).toBe("no-store");
  expect(first.init?.redirect).toBe("error");
  const apiCalls = calls.filter((call) => call.url.startsWith(ORIGIN));
  expect(apiCalls.every((call) => new Headers(call.init?.headers).get("x-serverless-authorization") === `Bearer ${value}`)).toBe(true);
  expect(new Headers(apiCalls[0].init?.headers).has("x-frontend-token")).toBe(false);
  expect(new Headers(apiCalls[1].init?.headers).get("x-frontend-token")).toBe("reviewer");
  expect(new Headers(apiCalls[2].init?.headers).get("authorization")).toBe("Bearer user");
  expect(apiCalls[1].init?.body).toBe("decision");
});

test("refreshes before expiry", async () => {
  const realNow = Date.now;
  const started = realNow();
  let now = started;
  Date.now = () => now;
  try {
    const { calls, fetcher } = mockFetch();
    const request = createApiTransport(ORIGIN, "google-id-token", true, fetcher);
    await request("/terms");
    now = started + 3_550_000;
    await request("/terms");
    expect(calls.filter((call) => call.url.includes("metadata.google.internal"))).toHaveLength(2);
  } finally {
    Date.now = realNow;
  }
});

for (const [name, response] of [
  ["unavailable", () => new Response("internal secret", { status: 503 })],
  ["wrong issuer response", () => new Response(token())],
  ["wrong audience", () => metadata(token("https://other.a.run.app"))],
  ["expired", () => metadata(token(ORIGIN, 1))],
  ["malformed", () => metadata("private invalid token")],
] as const) {
  test(`rejects ${name} without an unauthenticated API call or leaking error bodies`, async () => {
    const { calls, fetcher } = mockFetch(async () => response());
    const request = createApiTransport(ORIGIN, "google-id-token", true, fetcher);
    await expect(request("/terms")).rejects.toThrow("API identity token unavailable");
    expect(calls).toHaveLength(1);
  });
}

test("failed refresh can retry on the next request", async () => {
  let attempts = 0;
  const { calls, fetcher } = mockFetch(async () => ++attempts === 1 ? new Response(null, { status: 503 }) : metadata());
  const request = createApiTransport(ORIGIN, "google-id-token", true, fetcher);
  await expect(request("/terms")).rejects.toThrow();
  await request("/terms");
  expect(calls.filter((call) => call.url.startsWith(ORIGIN))).toHaveLength(1);
});

test("caller cancellation does not cancel another caller's shared token request", async () => {
  let release!: (response: Response) => void;
  const identity = new Promise<Response>((resolve) => { release = resolve; });
  const { calls, fetcher } = mockFetch(() => identity);
  const request = createApiTransport(ORIGIN, "google-id-token", true, fetcher);
  const controller = new AbortController();
  const first = request("/ask/stream", { signal: controller.signal });
  const rejected = expect(first).rejects.toThrow();
  const second = request("/terms");
  controller.abort();
  await rejected;
  release(metadata());
  await second;
  expect(calls.filter((call) => call.url.startsWith(ORIGIN)).map((call) => call.url)).toEqual([`${ORIGIN}/terms`]);
});

test("stream and multipart body pass through without buffering or replacing cancellation", async () => {
  const { calls, fetcher } = mockFetch();
  const request = createApiTransport(ORIGIN, "google-id-token", true, fetcher);
  const body = new FormData();
  body.set("text", "synthetic input");
  const controller = new AbortController();
  const response = await request("/recommend", { method: "POST", body, signal: controller.signal, cache: "no-store" });
  expect(response.body).not.toBeNull();
  expect(await response.text()).toBe("data: ready\n\n");
  expect(calls[1].init?.body).toBe(body);
  expect(calls[1].init?.signal).toBe(controller.signal);
  expect(new Headers(calls[1].init?.headers).has("content-type")).toBe(false);
});

test("invalid configuration or external request targets cannot receive a token", async () => {
  for (const [url, auth, cloud] of [
    [ORIGIN, "none", true], [ORIGIN, "typo", false], ["http://localhost:8080", "google-id-token", false],
    ["https://external.example", "google-id-token", true], [`${ORIGIN}/path`, "none", false],
  ] as const) expect(() => createApiTransport(url, auth, cloud)).toThrow();
  const { calls, fetcher } = mockFetch();
  const request = createApiTransport(ORIGIN, "google-id-token", true, fetcher);
  for (const path of ["https://external.example/terms", "//external.example/terms", "/\\external.example/terms"])
    await expect(request(path)).rejects.toThrow();
  expect(calls).toHaveLength(0);
  const controller = new AbortController();
  controller.abort();
  await expect(request("/terms", { signal: controller.signal })).rejects.toThrow();
  expect(calls).toHaveLength(0);
});

test("metadata timeout bounds a stalled token request", async () => {
  const calls: string[] = [];
  const fetcher = (url: string, init?: ApiRequestInit): Promise<Response> => {
    calls.push(url);
    return new Promise((_, reject) => {
      init?.signal?.addEventListener("abort", () => reject(init.signal?.reason), { once: true });
    });
  };
  const request = createApiTransport(ORIGIN, "google-id-token", true, fetcher);
  await expect(request("/terms")).rejects.toThrow("API identity token unavailable");
  expect(calls).toHaveLength(1);
});
