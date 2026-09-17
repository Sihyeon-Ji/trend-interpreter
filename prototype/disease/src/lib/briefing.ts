import { z } from "zod";
import { diseaseCounts } from "./selectors";
import type { Briefing, Dataset, Report } from "./types";

export const MAX_EVIDENCE_REPORTS = 24;
const findingSchema = z.object({
  title: z.string().min(1).max(180),
  detail: z.string().min(1).max(1800),
  reportIds: z.array(z.string()).min(1).max(8),
});
export const briefingSchema = z.object({
  headline: z.string().min(1).max(200),
  summary: z.string().min(1).max(2400),
  observations: z.array(findingSchema).min(1).max(6),
  hypotheses: z.array(findingSchema).max(4),
  actions: z.array(findingSchema).min(1).max(5),
  limitations: z.array(z.string().max(600)).min(1).max(8),
});

export const BASE_LIMITATIONS = [
  "Publication counts are not case counts, incidence, or proof of increasing transmission.",
  "This prototype covers selected official feeds, not every country or outbreak. Reporting delays and missing data are expected.",
  "Country shading is matched from report titles and indicates report focus, not infection boundaries or travel risk.",
  "Co-mentions do not establish epidemiological links. No calibrated pandemic probability or validated forecast is produced.",
];

export function selectEvidence(reports: Report[]): Report[] {
  const selected: Report[] = [];
  const seen = new Set<string>();
  const counts = new Map<string, number>();
  const sorted = [...reports].sort((a, b) =>
    b.publishedAt.localeCompare(a.publishedAt),
  );
  for (const report of sorted) {
    const key = `${report.sourceId}:${report.diseases[0] ?? "general"}`;
    if ((counts.get(key) ?? 0) >= 3) continue;
    selected.push(report);
    seen.add(report.id);
    counts.set(key, (counts.get(key) ?? 0) + 1);
    if (selected.length === MAX_EVIDENCE_REPORTS) return selected;
  }
  for (const report of sorted) {
    if (!seen.has(report.id)) selected.push(report);
    if (selected.length === MAX_EVIDENCE_REPORTS) break;
  }
  return selected;
}

export function evidenceBriefing(
  reports: Report[],
  dataset: Dataset,
): Briefing {
  const evidence = selectEvidence(reports);
  const diseases = diseaseCounts(reports);
  const sources = new Set(reports.map((report) => report.sourceId));
  const observations = diseases
    .slice(0, 4)
    .map(({ name, count }) => ({
      title: `${name} · ${count} reports`,
      detail: `${count} publications in the selected view mention ${name}. These may include repeat updates, preparedness guidance, or multi-disease bulletins. Review the cited publications before interpreting this as a change in transmission.`,
      reportIds: evidence
        .filter((report) => report.diseases.includes(name))
        .slice(0, 3)
        .map((report) => report.id),
    }))
    .filter((finding) => finding.reportIds.length);
  return {
    mode: "evidence",
    generatedAt: new Date().toISOString(),
    headline: "Your official-source evidence brief",
    summary: `${reports.length} matching publications across ${sources.size} agencies, with ${diseases.length} disease topics identified. ${evidence.length} reports were selected for review. This is a reproducible coverage summary; Gemini analysis is not configured.`,
    observations: observations.length
      ? observations
      : evidence.slice(0, 3).map((report) => ({
          title: report.title,
          detail:
            report.summary ||
            "Open the official publication for the full report.",
          reportIds: [report.id],
        })),
    hypotheses: [],
    actions: evidence.length
      ? [
          {
            title: "Review official assessments and advice",
            detail:
              "Open the cited reports to review each agency’s current assessment, recommended actions, scope, and publication date. Do not infer a risk level from the number of publications.",
            reportIds: evidence.slice(0, 3).map((report) => report.id),
          },
        ]
      : [],
    limitations: [
      ...BASE_LIMITATIONS,
      ...dataset.sources
        .filter((source) => source.status !== "live")
        .map((source) => `${source.name}: ${source.status}. ${source.message}`),
    ],
    evidence,
    steps: [
      "Collected matching official publications",
      "Grouped disease mentions",
      "Selected source-diverse evidence",
      "Generated a deterministic evidence brief",
    ],
  };
}

export function validateBriefing(value: unknown, evidence: Report[]) {
  const parsed = briefingSchema.parse(value);
  const allowed = new Set(evidence.map((report) => report.id));
  for (const finding of [
    ...parsed.observations,
    ...parsed.hypotheses,
    ...parsed.actions,
  ]) {
    if (finding.reportIds.some((id) => !allowed.has(id)))
      throw new Error("The analysis included an unsupported source reference.");
  }
  return parsed;
}
