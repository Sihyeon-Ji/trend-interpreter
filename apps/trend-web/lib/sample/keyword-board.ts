/* 예시 데이터 모드의 키워드 대시보드. 실제 지역 판정·목록 나누기는 백엔드 pipeline/dashboard.py 의 규칙이고,
   여기는 그 규칙을 예시 사전(SAMPLE_RECORDS)에 그대로 옮겨 모델·서버 없이 화면을 열어 보게 할 뿐이다. */
import { TARGET_REGIONS } from "../reader";
import type { KeywordBoard, KeywordCard, SourceCount, TermRecord } from "../types";
import { SAMPLE_RECORDS } from "./dictionary";

const LANG_REGION: Record<string, string> = { ko: "KR", ja: "JP", id: "ID", th: "TH", vi: "VN", zh: "TW", tl: "PH", fil: "PH", ms: "MY" };
// 표제어 언어의 나라로 두는 것은 그 나라 글자로 쓴 말만 (백엔드 dashboard.term_regions 와 같은 규칙)
const SCRIPT: Record<string, RegExp> = { ko: /[가-힣]/, ja: /[\u3040-\u30ff\u4e00-\u9fff]/, zh: /[\u4e00-\u9fff]/, th: /[\u0e00-\u0e7f]/ };
const LATIN_ONLY = /^[\x00-\x7f\u00c0-\u024f\s]+$/;
const LIST_MAX = 30;
const DIFFUSION_ORDER: Record<string, number> = { spreading: 0, underground: 1, mainstream: 2 };
const LIFECYCLE_ORDER: Record<string, number> = { emerging: 0, rising: 0, peak: 1, steady: 2 };

function regionsOf(r: TermRecord): string[] {
  const used = new Set(r.usage.map((u) => u.segment.region).filter(Boolean));   // '' 는 나라 정보가 없는 것
  const regions = TARGET_REGIONS.filter((x) => used.has(x));
  const lang = r.term.lang ?? "ko";
  if (!used.size) {
    if (TARGET_REGIONS.includes(LANG_REGION[lang]) && SCRIPT[lang]?.test(r.term.canonical)) regions.push(LANG_REGION[lang]);
    else if (LATIN_ONLY.test(r.term.canonical)) return ["GLOBAL"];
  }
  if (used.has("GLOBAL") || (!regions.length && used.size && lang === "en")) regions.push("GLOBAL");
  return regions;
}

function toCard(r: TermRecord): KeywordCard {
  const m = r.meanings.find((x) => !x.valid_to) ?? r.meanings.at(-1);
  const weekly = r.weekly.slice(-12);
  const counts = new Map<string, number>();
  for (const e of r.evidences) if (e.kind === "community") counts.set(e.source_domain, (counts.get(e.source_domain) ?? 0) + 1);
  const communities: SourceCount[] = [...counts].sort((a, b) => b[1] - a[1]).slice(0, 5).map(([domain, count]) => ({ domain, count }));
  const recent = [...r.evidences].filter((e) => e.kind !== "datalab").sort((a, b) => b.observed_at.localeCompare(a.observed_at)).slice(0, 5);
  return {
    term_id: r.term.term_id, canonical: r.term.canonical, lang: r.term.lang ?? "ko", category: r.category,
    gloss_ko: r.ko?.definition ?? m?.definition ?? "", gloss_en: r.en?.definition ?? m?.definition ?? "",
    regions: regionsOf(r), lifecycle: r.term.lifecycle ?? "unknown", diffusion: r.term.diffusion ?? null,
    risk_level: r.term.risk_level ?? null, risk_reasons: r.term.risk_reasons ?? [],
    weekly, mentions_4w: weekly.slice(-4).reduce((a, p) => a + p.count, 0),
    risk_checked_at: r.term.risk_checked_at ?? null,
    search: [], gen_peaks: [], communities, tone: { positive: 0, neutral: 0, negative: 0 },
    evidences: recent.map((e) => ({ kind: e.kind, source_domain: e.source_domain, title: e.title ?? e.excerpt ?? "", url: e.url, observed_at: e.observed_at })),
    last_seen: r.term.last_seen ?? null,
  };
}

const fading = (c: KeywordCard) => c.diffusion === "fading" || c.lifecycle === "declining" || c.lifecycle === "dormant";

export function sampleKeywordBoard(regions: string[]): KeywordBoard {
  const cards = SAMPLE_RECORDS.filter((r) => r.term.status === "verified").map(toCard).filter((c) => c.regions.length);
  const known = [...TARGET_REGIONS, "GLOBAL"];
  const chosen = known.filter((r) => regions.includes(r));
  const picked = chosen.length ? chosen : TARGET_REGIONS;
  const inView = cards.filter((c) => c.regions.some((r) => picked.includes(r)));
  const byMentions = (a: KeywordCard, b: KeywordCard) => b.mentions_4w - a.mentions_4w;
  return {
    generated_at: "2026-09-13T21:10:00Z",
    regions: picked,
    counts: Object.fromEntries(known.map((r) => [r, cards.filter((c) => c.regions.includes(r)).length])),
    rising: inView.filter((c) => !fading(c) && c.risk_level !== "avoid")
      .sort((a, b) => (DIFFUSION_ORDER[a.diffusion ?? ""] ?? 3) - (DIFFUSION_ORDER[b.diffusion ?? ""] ?? 3) || (LIFECYCLE_ORDER[a.lifecycle] ?? 3) - (LIFECYCLE_ORDER[b.lifecycle] ?? 3) || byMentions(a, b))
      .slice(0, LIST_MAX),
    fading: inView.filter((c) => fading(c) && c.risk_level !== "avoid").sort((a, b) => (b.last_seen ?? "").localeCompare(a.last_seen ?? "")).slice(0, LIST_MAX),
    caution: inView.filter((c) => c.risk_level === "caution" || c.risk_level === "avoid")
      .sort((a, b) => Number(a.risk_level !== "avoid") - Number(b.risk_level !== "avoid") || byMentions(a, b)).slice(0, LIST_MAX),
  };
}

export function sampleSignals(termId: string): KeywordCard | null {
  const r = SAMPLE_RECORDS.find((x) => x.term.term_id === termId);
  return r && r.term.status === "verified" ? toCard(r) : null;   // 백엔드처럼 확인된 말만 (확인 중인 말은 404)
}
