import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { dataset } from "./fixtures";

vi.mock("../src/lib/dataset", () => ({
  getDataset: vi.fn(async () => dataset),
}));
vi.mock("../src/lib/agent", () => ({
  runBriefingAgent: vi.fn(async () => ({ mode: "evidence" })),
}));

beforeEach(() => {
  vi.resetModules();
  vi.stubEnv("ANALYSIS_ACCESS_TOKEN", "");
});
afterEach(() => {
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
});
const validBody = {
  filters: {
    search: "",
    disease: "all",
    source: "all",
    country: "all",
    days: 90,
  },
};

async function post(body: string, headers: Record<string, string> = {}) {
  const { POST } = await import("../src/app/api/briefing/route");
  return POST(
    new Request("http://localhost/api/briefing", {
      method: "POST",
      body,
      headers: { host: "localhost", ...headers },
    }),
  );
}

describe("briefing API", () => {
  it("rejects malformed input", async () => {
    expect((await post("not json")).status).toBe(400);
  });
  it("rejects unsupported reporting windows", async () => {
    expect(
      (
        await post(
          JSON.stringify({ filters: { ...validBody.filters, days: 999 } }),
        )
      ).status,
    ).toBe(400);
  });
  it("caps request size", async () => {
    expect((await post("x".repeat(6000))).status).toBe(413);
  });
  it.each(["https://evil.test", "not a URL"])(
    "rejects an untrusted origin: %s",
    async (origin) => {
      expect((await post(JSON.stringify(validBody), { origin })).status).toBe(
        403,
      );
    },
  );
  it("enforces a configured access token", async () => {
    vi.stubEnv("ANALYSIS_ACCESS_TOKEN", "test-only-secret");
    expect((await post(JSON.stringify(validBody))).status).toBe(401);
  });
  it("runs an authorized request and throttles repeated requests", async () => {
    vi.spyOn(Date, "now").mockReturnValue(Date.parse(dataset.collectedAt));
    vi.stubEnv("ANALYSIS_ACCESS_TOKEN", "test-only-secret");
    expect(
      (
        await post(JSON.stringify(validBody), {
          authorization: "Bearer test-only-secret",
        })
      ).status,
    ).toBe(200);
    expect(
      (
        await post(JSON.stringify(validBody), {
          authorization: "Bearer test-only-secret",
        })
      ).status,
    ).toBe(429);
  });
  it("does not analyze an empty evidence set", async () => {
    expect(
      (
        await post(
          JSON.stringify({
            filters: { ...validBody.filters, search: "no-such-report-xyz" },
          }),
        )
      ).status,
    ).toBe(422);
  });
});
