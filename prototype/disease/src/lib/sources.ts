import { createHash } from "node:crypto";
import { XMLParser, XMLValidator } from "fast-xml-parser";
import { decode } from "he";
import { z } from "zod";
import { enrichReport } from "./classify";
import type { Report, SourceId, SourceStatus } from "./types";

export const SOURCE_DEFINITIONS = [
  {
    id: "who",
    name: "WHO",
    organization: "World Health Organization",
    region: "Global",
    homepage: "https://www.who.int/emergencies/disease-outbreak-news",
    endpoint:
      "https://www.who.int/api/hubs/diseaseoutbreaknews?$orderby=PublicationDate%20desc&$top=100",
    format: "who",
    host: "www.who.int",
  },
  {
    id: "cdc",
    name: "CDC",
    organization: "Centers for Disease Control and Prevention",
    region: "Global travel notices",
    homepage: "https://wwwnc.cdc.gov/travel/notices",
    endpoint: "https://wwwnc.cdc.gov/travel/rss/notices.xml",
    format: "rss",
    host: "wwwnc.cdc.gov",
  },
  {
    id: "ecdc",
    name: "ECDC",
    organization: "European Centre for Disease Prevention and Control",
    region: "Europe · weekly threat reports",
    homepage: "https://www.ecdc.europa.eu/en/current-threats",
    endpoint: "https://www.ecdc.europa.eu/en/taxonomy/term/1505/feed",
    format: "rss",
    host: "www.ecdc.europa.eu",
  },
  {
    id: "ukhsa",
    name: "UKHSA",
    organization: "UK Health Security Agency",
    region: "United Kingdom · official news",
    homepage:
      "https://www.gov.uk/government/organisations/uk-health-security-agency",
    endpoint:
      "https://www.gov.uk/search/news-and-communications.atom?organisations%5B%5D=uk-health-security-agency",
    format: "atom",
    host: "www.gov.uk",
  },
  {
    id: "kdca",
    name: "KDCA",
    organization: "Korea Disease Control and Prevention Agency",
    region: "Republic of Korea · official news",
    homepage: "https://www.kdca.go.kr/kdca/4912/subview.do",
    endpoint: "https://www.kdca.go.kr/bbs/kdca/41/rssList.do?row=50",
    format: "rss",
    host: "www.kdca.go.kr",
  },
] as const;

export type SourceDefinition = (typeof SOURCE_DEFINITIONS)[number];
const MAX_RESPONSE_BYTES = 8_000_000;
const FETCH_TIMEOUT_MS = 12_000;
const MAX_REPORTS_PER_SOURCE = 100;

export function plainText(input: unknown, maxLength = 8000): string {
  if (typeof input !== "string") return "";
  return decode(
    input
      .replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, " ")
      .replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, " ")
      .replace(/<[^>]+>/g, " "),
  )
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, maxLength);
}

function safeUrl(input: unknown, source: SourceDefinition): string | null {
  if (typeof input !== "string" || !input.trim()) return null;
  try {
    const url = new URL(input, source.homepage);
    if (
      !["http:", "https:"].includes(url.protocol) ||
      url.hostname !== source.host ||
      url.username ||
      url.password
    )
      return null;
    url.protocol = "https:";
    return url.toString();
  } catch {
    return null;
  }
}

function makeReport(
  source: SourceDefinition,
  input: {
    title: unknown;
    summary: unknown;
    date: unknown;
    url: unknown;
    assessment?: unknown;
    advice?: unknown;
  },
): Report | null {
  const title = plainText(input.title, 500);
  const url = safeUrl(input.url, source);
  const timestamp =
    typeof input.date === "string" ? Date.parse(input.date) : NaN;
  if (
    !title ||
    !url ||
    !Number.isFinite(timestamp) ||
    timestamp > Date.now() + 86_400_000
  )
    return null;
  return enrichReport({
    id: `${source.id}-${createHash("sha256").update(url).digest("hex").slice(0, 16)}`,
    sourceId: source.id,
    title,
    summary: plainText(input.summary, 6000),
    publishedAt: new Date(timestamp).toISOString(),
    url,
    assessment: plainText(input.assessment, 8000),
    advice: plainText(input.advice, 8000),
  });
}

const whoSchema = z.object({
  value: z.array(
    z.object({
      Title: z.string(),
      PublicationDate: z.string(),
      UrlName: z.string(),
      Summary: z.string().nullish(),
      Assessment: z.string().nullish(),
      Advice: z.string().nullish(),
    }),
  ),
});

export function parseWho(body: string): Report[] {
  const { value } = whoSchema.parse(JSON.parse(body));
  const source = SOURCE_DEFINITIONS[0];
  return value
    .map((entry) =>
      makeReport(source, {
        title: entry.Title,
        summary: entry.Summary,
        date: entry.PublicationDate,
        url: `https://www.who.int/emergencies/disease-outbreak-news/item/${encodeURIComponent(entry.UrlName)}`,
        assessment: entry.Assessment,
        advice: entry.Advice,
      }),
    )
    .filter((report): report is Report => report !== null);
}

type XmlEntry = Record<string, unknown>;
function arrayOf<T>(value: T | T[] | undefined): T[] {
  return value === undefined ? [] : Array.isArray(value) ? value : [value];
}
function xmlText(value: unknown): unknown {
  return typeof value === "object" && value !== null
    ? (value as XmlEntry)["#text"]
    : value;
}

export function parseFeed(body: string, source: SourceDefinition): Report[] {
  if (/<!DOCTYPE|<!ENTITY/i.test(body))
    throw new Error("Unsupported feed declaration.");
  if (XMLValidator.validate(body.trim()) !== true)
    throw new Error("Invalid XML feed.");
  const parsed = new XMLParser({
    ignoreAttributes: false,
    parseTagValue: false,
    processEntities: true,
  }).parse(body.trim());
  const entries =
    source.format === "atom"
      ? arrayOf<XmlEntry>(parsed.feed?.entry)
      : arrayOf<XmlEntry>(parsed.rss?.channel?.item);
  return entries
    .slice(0, MAX_REPORTS_PER_SOURCE)
    .map((entry) => {
      const link =
        source.format === "atom"
          ? arrayOf<XmlEntry>(entry.link as XmlEntry | XmlEntry[]).find(
              (item) => item["@_rel"] === "alternate" || !item["@_rel"],
            )?.["@_href"]
          : entry.link;
      return makeReport(source, {
        title: xmlText(entry.title),
        summary: xmlText(entry.description ?? entry.summary ?? entry.content),
        date:
          entry.pubDate ?? entry.published ?? entry.updated ?? entry["dc:date"],
        url: link,
      });
    })
    .filter((report): report is Report => report !== null);
}

async function readLimited(response: Response): Promise<string> {
  if (!response.body) throw new Error("Empty response.");
  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > MAX_RESPONSE_BYTES) {
        await reader.cancel();
        throw new Error("Feed exceeds size limit.");
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  return Buffer.concat(chunks).toString("utf8");
}

export async function fetchSource(source: SourceDefinition): Promise<Report[]> {
  const response = await fetch(source.endpoint, {
    signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
    cache: "no-store",
    redirect: "error",
    headers: {
      "User-Agent": "OutbreakAtlas/0.1 (public-health research prototype)",
      Accept:
        "application/json, application/atom+xml, application/rss+xml, application/xml, text/xml",
    },
  });
  if (!response.ok) throw new Error(`Source returned HTTP ${response.status}.`);
  const body = await readLimited(response);
  const reports =
    source.format === "who" ? parseWho(body) : parseFeed(body, source);
  if (!reports.length)
    throw new Error("Source did not return usable, dated reports.");
  return [...new Map(reports.map((report) => [report.id, report])).values()];
}

export function statusFor(
  source: SourceDefinition,
  reports: Report[],
  fields: Pick<
    SourceStatus,
    "status" | "checkedAt" | "retrievedAt" | "message"
  >,
): SourceStatus {
  return {
    id: source.id as SourceId,
    name: source.name,
    organization: source.organization,
    region: source.region,
    homepage: source.homepage,
    reportCount: reports.length,
    latestPublishedAt:
      reports
        .map((report) => report.publishedAt)
        .sort()
        .at(-1) ?? null,
    ...fields,
  };
}
