import { describe, expect, it } from "vitest";
import {
  evidenceBriefing,
  selectEvidence,
  validateBriefing,
} from "../src/lib/briefing";
import { executeEvidenceTool } from "../src/lib/agent";
import {
  DEFAULT_FILTERS,
  filterReports,
  weeklyCounts,
} from "../src/lib/selectors";
import { dataset, report } from "./fixtures";

describe("report selection", () => {
  const now = Date.parse(dataset.collectedAt);
  it("applies filters together and excludes future and invalid dates", () => {
    const reports = [
      report,
      { ...report, id: "future", publishedAt: "2027-01-01" },
      { ...report, id: "invalid", publishedAt: "invalid" },
    ];
    expect(
      filterReports(
        reports,
        {
          ...DEFAULT_FILTERS,
          disease: "Ebola",
          country: "CD",
          search: "surveillance",
        },
        now,
      ),
    ).toEqual([report]);
    expect(
      filterReports(reports, { ...DEFAULT_FILTERS, source: "cdc" }, now),
    ).toEqual([]);
  });
  it("uses the actual current window, not the newest report as the present", () => {
    expect(
      filterReports(
        [{ ...report, publishedAt: "2025-01-01" }],
        DEFAULT_FILTERS,
        now,
      ),
    ).toEqual([]);
  });
  it("counts each publication once in weekly bars", () => {
    expect(
      weeklyCounts([report, { ...report, id: "second" }], 90, now).reduce(
        (sum, b) => sum + b.count,
        0,
      ),
    ).toBe(2);
  });
  it("limits agent evidence and preserves source diversity", () => {
    const reports = Array.from({ length: 40 }, (_, i) => ({
      ...report,
      id: `who-${i}`,
    }));
    const selected = selectEvidence([
      ...reports,
      { ...report, id: "cdc-1", sourceId: "cdc" },
    ]);
    expect(selected).toHaveLength(24);
    expect(selected.some((r) => r.id === "cdc-1")).toBe(true);
    expect(new Set(selected.map((r) => r.id)).size).toBe(24);
  });
});

describe("evidence and agent trust boundaries", () => {
  it("labels keyless output honestly and generates no forecasts", () => {
    const result = evidenceBriefing([report], dataset);
    expect(result.mode).toBe("evidence");
    expect(result.hypotheses).toEqual([]);
    expect(result.summary).toContain("not configured");
    expect(result.observations[0].reportIds).toEqual([report.id]);
  });
  it("rejects hallucinated citations instead of silently dropping them", () => {
    const valid = evidenceBriefing([report], dataset);
    expect(() =>
      validateBriefing(
        {
          ...valid,
          observations: [
            { title: "Claim", detail: "A statement", reportIds: ["invented"] },
          ],
        },
        [report],
      ),
    ).toThrow("unsupported source reference");
  });
  it("accepts findings with valid citations", () => {
    expect(
      validateBriefing(evidenceBriefing([report], dataset), [report])
        .observations,
    ).toHaveLength(1);
  });
  it("rejects findings without references", () => {
    const valid = evidenceBriefing([report], dataset);
    expect(() =>
      validateBriefing(
        {
          ...valid,
          actions: [{ title: "Action", detail: "Detail", reportIds: [] }],
        },
        [report],
      ),
    ).toThrow();
  });
  it("restricts reading to the evidence set", () => {
    expect(
      executeEvidenceTool(
        "read_report",
        { reportId: report.id },
        [report],
        [report],
        dataset,
      ),
    ).toEqual(report);
    expect(
      executeEvidenceTool(
        "read_report",
        { reportId: "https://evil.test" },
        [report],
        [report],
        dataset,
      ),
    ).toHaveProperty("error");
    expect(
      executeEvidenceTool(
        "run_shell",
        { command: "anything" },
        [report],
        [report],
        dataset,
      ),
    ).toHaveProperty("error");
  });
  it("exposes publication counts with an explicit incidence caveat", () => {
    expect(
      executeEvidenceTool("compare_coverage", {}, [report], [report], dataset),
    ).toMatchObject({
      matchingPublications: 1,
      caveat: expect.stringContaining("not cases"),
    });
  });
});
