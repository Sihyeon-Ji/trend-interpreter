/* 미리보기가 나중에 받는 항목 요약 — /terms/{id}(수십 KB, 커뮤니티 근거 포함)를 화면에 필요한 것만 추려 브라우저로 보낸다.
   커뮤니티 근거는 여기서 걸러져 브라우저에 아예 가지 않는다. */
import type { TermRecord } from "@/lib/types";
import { type SourceRef, thumbUrl, visibleEvidence, youtubeId } from "./f-report";

export interface MeaningLite { definition: string; expansion: string | null; origin: string | null; nuance: string | null; plain: string | null }
export interface TermDetail {
  id: string;
  name: string;
  lang: string;
  aliases: string[];
  category: string;
  status: string;
  risk: "none" | "caution" | "avoid" | null;
  ko: MeaningLite | null;
  en: MeaningLite | null;
  media: { kind: "image" | "video"; url: string; page_url: string; title: string; license: string; attribution: string } | null;
  video: { url: string; thumb: string; title: string } | null;
  sources: SourceRef[];
  firstSeen: string | null;
}

const clean = (s: string | null | undefined) => {
  const t = (s ?? "").trim();
  return !t || t.toLowerCase() === "unknown" ? null : t;
};

export function toDetail(r: TermRecord): TermDetail {
  const current = r.meanings.find((m) => !m.valid_to) ?? r.meanings.at(-1) ?? null;
  const ko: MeaningLite | null = r.ko
    ? { definition: r.ko.definition, expansion: clean(r.ko.expansion), origin: clean(r.ko.origin), nuance: clean(r.ko.nuance), plain: clean(r.ko.plain) ?? clean(r.plain) }
    : current
      ? { definition: current.definition, expansion: clean(current.expansion), origin: clean(current.origin), nuance: clean(current.nuance), plain: clean(r.plain) }
      : null;
  const en: MeaningLite | null = r.en ? { definition: r.en.definition, expansion: clean(r.en.expansion), origin: clean(r.en.origin), nuance: clean(r.en.nuance), plain: clean(r.en.plain) } : null;
  const visible = visibleEvidence(r.evidences);
  const short = visible.find((e) => e.kind === "short" && youtubeId(e.url));
  const vid = short ? youtubeId(short.url) : null;
  const m = r.media?.[0] ?? null;
  return {
    id: r.term.term_id,
    name: r.term.canonical,
    lang: r.term.lang ?? "",
    aliases: (r.term.aliases ?? []).filter((a) => a && a !== r.term.canonical),
    category: r.category,
    status: r.term.status ?? "verified",
    risk: r.term.risk_level ?? null,
    ko,
    en,
    media: m ? { kind: m.kind, url: m.url, page_url: m.page_url, title: m.title, license: m.license, attribution: m.attribution } : null,
    video: short && vid ? { url: short.url, thumb: thumbUrl(vid), title: short.title ?? "" } : null,
    sources: visible.slice(0, 12).map((e) => ({ kind: e.kind, domain: e.source_domain, title: e.title ?? e.source_domain, url: e.url, at: e.observed_at })),
    firstSeen: r.term.first_seen ?? null,
  };
}
