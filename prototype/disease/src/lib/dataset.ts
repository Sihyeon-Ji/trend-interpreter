import snapshot from "../data/snapshot.json";
import { fetchSource, SOURCE_DEFINITIONS, statusFor } from "./sources";
import type { Dataset } from "./types";

export const CACHE_TTL_MS = 15 * 60 * 1000;
let cached: Dataset | undefined;
let expiresAt = 0;
let pending: Promise<Dataset> | undefined;

export async function collectDataset(
  previous: Dataset = snapshot as Dataset,
): Promise<Dataset> {
  const checkedAt = new Date().toISOString();
  const results = await Promise.all(
    SOURCE_DEFINITIONS.map(async (source) => {
      try {
        const reports = await fetchSource(source);
        return {
          reports,
          status: statusFor(source, reports, {
            status: "live",
            checkedAt,
            retrievedAt: checkedAt,
            message:
              "Official feed retrieved successfully. Publication schedules vary by source.",
          }),
        };
      } catch (error) {
        const reports = previous.reports.filter(
          (report) => report.sourceId === source.id,
        );
        const prior = previous.sources.find((item) => item.id === source.id);
        const reason =
          error instanceof Error &&
          /^(Source |Feed |Invalid |Unsupported |Empty )/.test(error.message)
            ? error.message
            : "Source could not be reached within the time limit.";
        return {
          reports,
          status: statusFor(source, reports, {
            status: reports.length ? "snapshot" : "unavailable",
            checkedAt,
            retrievedAt: reports.length
              ? (prior?.retrievedAt ?? previous.collectedAt)
              : null,
            message: reports.length
              ? `${reason} Showing the last successful capture; this is not a live feed.`
              : reason,
          }),
        };
      }
    }),
  );
  return {
    reports: results
      .flatMap((result) => result.reports)
      .sort((a, b) => b.publishedAt.localeCompare(a.publishedAt)),
    sources: results.map((result) => result.status),
    collectedAt: checkedAt,
  };
}

export async function getDataset(): Promise<Dataset> {
  if (cached && Date.now() < expiresAt) return cached;
  if (pending) return pending;
  pending = collectDataset(cached)
    .then((dataset) => {
      cached = dataset;
      expiresAt = Date.now() + CACHE_TTL_MS;
      return dataset;
    })
    .finally(() => {
      pending = undefined;
    });
  return pending;
}
