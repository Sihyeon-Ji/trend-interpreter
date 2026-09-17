import type { Filters, Report } from "./types";

export const DAY_MS = 86_400_000;
export const DEFAULT_FILTERS: Filters = {
  search: "",
  disease: "all",
  source: "all",
  country: "all",
  days: 90,
};

export function filterReports(
  reports: Report[],
  filters: Filters,
  now = Date.now(),
): Report[] {
  const cutoff = now - filters.days * DAY_MS;
  const query = filters.search.trim().toLowerCase();
  return reports.filter((report) => {
    const date = Date.parse(report.publishedAt);
    if (!Number.isFinite(date) || date > now || date < cutoff) return false;
    if (filters.disease !== "all" && !report.diseases.includes(filters.disease))
      return false;
    if (filters.source !== "all" && report.sourceId !== filters.source)
      return false;
    if (
      filters.country !== "all" &&
      !report.countries.some((country) => country.code === filters.country)
    )
      return false;
    return (
      !query ||
      `${report.title} ${report.summary} ${report.diseases.join(" ")} ${report.countries.map((c) => c.name).join(" ")}`
        .toLowerCase()
        .includes(query)
    );
  });
}

export function diseaseCounts(reports: Report[]) {
  const counts = new Map<string, number>();
  for (const report of reports)
    for (const disease of report.diseases)
      counts.set(disease, (counts.get(disease) ?? 0) + 1);
  return [...counts]
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name));
}

export function weeklyCounts(
  reports: Report[],
  days: number,
  now = Date.now(),
) {
  const bucketCount = Math.ceil(days / 7);
  const end = Date.UTC(
    new Date(now).getUTCFullYear(),
    new Date(now).getUTCMonth(),
    new Date(now).getUTCDate() + 1,
  );
  const start = end - bucketCount * 7 * DAY_MS;
  const buckets = Array.from({ length: bucketCount }, (_, index) => ({
    date: new Date(start + index * 7 * DAY_MS).toISOString(),
    count: 0,
  }));
  for (const report of reports) {
    const date = Date.parse(report.publishedAt);
    if (date > now || date < now - days * DAY_MS) continue;
    const index = Math.floor((date - start) / (7 * DAY_MS));
    if (index >= 0 && index < buckets.length) buckets[index].count++;
  }
  return buckets;
}

export function formatDate(
  value: string,
  options?: Intl.DateTimeFormatOptions,
) {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
    ...options,
  }).format(new Date(value));
}

export function relativeDate(value: string, now = Date.now()) {
  const days = Math.floor((now - Date.parse(value)) / DAY_MS);
  if (days <= 0) return "Today";
  if (days === 1) return "1 day ago";
  return `${days} days ago`;
}
