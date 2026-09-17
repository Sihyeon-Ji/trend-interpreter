export type SourceId = "who" | "cdc" | "ecdc" | "ukhsa" | "kdca";

export interface Country {
  code: string;
  name: string;
  latitude: number;
  longitude: number;
}

export interface Report {
  id: string;
  sourceId: SourceId;
  title: string;
  summary: string;
  publishedAt: string;
  url: string;
  diseases: string[];
  countries: Country[];
  topics: string[];
  assessment: string;
  advice: string;
}

export interface SourceStatus {
  id: SourceId;
  name: string;
  organization: string;
  region: string;
  homepage: string;
  status: "live" | "snapshot" | "unavailable";
  checkedAt: string;
  retrievedAt: string | null;
  latestPublishedAt: string | null;
  reportCount: number;
  message: string;
}

export interface Dataset {
  reports: Report[];
  sources: SourceStatus[];
  collectedAt: string;
}

export interface Filters {
  search: string;
  disease: string;
  source: string;
  country: string;
  days: number;
}

export interface Finding {
  title: string;
  detail: string;
  reportIds: string[];
}

export interface Briefing {
  mode: "gemini" | "evidence";
  generatedAt: string;
  headline: string;
  summary: string;
  observations: Finding[];
  hypotheses: Finding[];
  actions: Finding[];
  limitations: string[];
  evidence: Report[];
  steps: string[];
}
