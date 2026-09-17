import { enrichReport } from "../src/lib/classify";
import type { Dataset } from "../src/lib/types";

export const report = enrichReport({
  id: "who-example",
  sourceId: "who",
  title: "Ebola disease - Democratic Republic of the Congo",
  summary: "A public health update with surveillance and cross-border context.",
  publishedAt: "2026-09-10T00:00:00.000Z",
  url: "https://www.who.int/emergencies/disease-outbreak-news/item/example",
  assessment: "An official assessment.",
  advice: "An official response recommendation.",
});
export const dataset: Dataset = {
  reports: [report],
  collectedAt: "2026-09-16T00:00:00.000Z",
  sources: [
    {
      id: "who",
      name: "WHO",
      organization: "World Health Organization",
      region: "Global",
      homepage: "https://www.who.int",
      status: "live",
      checkedAt: "2026-09-16T00:00:00.000Z",
      retrievedAt: "2026-09-16T00:00:00.000Z",
      latestPublishedAt: report.publishedAt,
      reportCount: 1,
      message: "Retrieved.",
    },
  ],
};
