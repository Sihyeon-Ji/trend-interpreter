import { afterEach, describe, expect, it, vi } from "vitest";
import { dataset, report } from "./fixtures";

vi.mock("../src/lib/sources", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../src/lib/sources")>()),
  fetchSource: vi.fn(),
}));

afterEach(() => {
  vi.resetModules();
  vi.clearAllMocks();
});

describe("collection resilience", () => {
  it("keeps an unavailable source separate from an archived official capture", async () => {
    const { fetchSource } = await import("../src/lib/sources");
    vi.mocked(fetchSource).mockRejectedValue(
      new Error("Source returned HTTP 503."),
    );
    const { collectDataset } = await import("../src/lib/dataset");
    const result = await collectDataset(dataset);
    expect(result.reports).toEqual([report]);
    expect(result.sources.find((s) => s.id === "who")).toMatchObject({
      status: "snapshot",
      retrievedAt: dataset.sources[0].retrievedAt,
    });
    expect(result.sources.find((s) => s.id === "kdca")).toMatchObject({
      status: "unavailable",
      reportCount: 0,
      retrievedAt: null,
    });
  });
  it("deduplicates concurrent collection requests", async () => {
    const { fetchSource } = await import("../src/lib/sources");
    vi.mocked(fetchSource).mockImplementation(async (source) => [
      { ...report, id: `${source.id}-1`, sourceId: source.id },
    ]);
    const { getDataset } = await import("../src/lib/dataset");
    const [first, second] = await Promise.all([getDataset(), getDataset()]);
    expect(fetchSource).toHaveBeenCalledTimes(5);
    expect(first).toBe(second);
    await getDataset();
    expect(fetchSource).toHaveBeenCalledTimes(5);
  });
});
