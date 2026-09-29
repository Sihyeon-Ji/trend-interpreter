/* 사전 색인의 행 모델과 거르기·정렬. 서버가 사전 기록(TermRecord)을 행 하나에 필요한 칸만 남겨 넘긴다 —
   기록 전체(근거·주간 수·뜻 버전)를 브라우저로 보내면 운영 데이터 148개에 2.26MB 였다(2026-09-29 검토). */
import type { Diffusion, RiskLevel } from "../contract/types";
import { currentMeaning, textFor } from "../explain";
import type { Locale } from "../i18n";
import type { Category, Generation, Lifecycle, TermRecord } from "../types";
import { lastUsedOf, termRegions } from "./regions";

/** 뜻 한 줄: 풀이(expansion)와 뜻을 잇는다. 끝 문장부호를 떼고, 뜻에 이미 풀이가 들어 있으면 풀이를 뺀다.
 *  위키 문서 제목이 풀이로 들어온 것('… (disambiguation)')은 버린다 — 마침표 두 개, 같은 말 반복이 나가던 것. */
export function glossParts(r: TermRecord, locale: Locale): { expansion: string | null; definition: string | null } {
  const tx = textFor(r, locale);
  const definition = (tx?.definition ?? currentMeaning(r)?.definition ?? "").trim() || null;
  let expansion = (tx?.expansion ?? "").trim().replace(/[.。]+$/, "") || null;
  if (expansion && (/\(disambiguation\)/i.test(expansion) || (definition && definition.includes(expansion)))) expansion = null;
  return { expansion, definition };
}

export type RiskFilter = "none" | "caution" | "avoid" | "unknown" | "unchecked";
export type SortKey = "name" | "used" | "changed" | "unfamiliar";

export interface DictionaryRow {
  term_id: string;
  canonical: string;
  lang: string;
  aliases: string[];
  expansion: string | null;
  definition: string | null;
  meaning_lang: string | null;   // 뜻이 화면 언어가 아닌 원문으로 나갈 때의 말(영어 화면의 한국어 뜻)
  category: Category;
  diffusion: Diffusion | null;
  lifecycle: Lifecycle;
  regions: string[];
  last_used: string | null;
  changed: string | null;        // 새로 실리거나 뜻이 바뀐 날(현재 뜻의 시작)
  risk_level: RiskLevel | null;
  risk_checked_at: string | null;
  generations: Generation[];
  search: string;                // 표제어·다른 표기·뜻을 소문자로 이은 것
}

export function toRow(r: TermRecord, locale: Locale): DictionaryRow {
  const m = currentMeaning(r);
  const { expansion, definition } = glossParts(r, locale);
  const translated = locale === "en" ? !!r.en : !!r.ko || (r.term.lang ?? "ko") === "ko";
  return {
    term_id: r.term.term_id, canonical: r.term.canonical, lang: r.term.lang ?? "ko", aliases: r.term.aliases ?? [],
    expansion, definition, meaning_lang: translated ? null : "ko",
    category: r.category, diffusion: r.term.diffusion ?? null, lifecycle: r.term.lifecycle ?? "unknown",
    regions: termRegions(r), last_used: lastUsedOf(r), changed: m?.valid_from ?? null,
    risk_level: r.term.risk_level ?? null, risk_checked_at: r.term.risk_checked_at ?? null,
    generations: m?.generations ?? [],
    search: [r.term.canonical, ...(r.term.aliases ?? []), expansion ?? "", definition ?? "", m?.definition ?? ""].join(" ").toLowerCase(),
  };
}

export function riskKey(r: Pick<DictionaryRow, "risk_level" | "risk_checked_at">): RiskFilter {
  if (r.risk_level === "caution" || r.risk_level === "avoid" || r.risk_level === "none") return r.risk_level;
  return r.risk_checked_at ? "unknown" : "unchecked";
}

/** 가나다순에서 글자 갈래의 순서: 화면 언어의 글자가 먼저, 일본어·태국어 같은 다른 글자는 뒤에 모인다. */
function scriptRank(s: string, locale: Locale): number {
  const c = s.trim().charAt(0);
  if (/[가-힣ㄱ-ㅎ]/.test(c)) return locale === "ko" ? 0 : 1;
  if (/[a-zÀ-ɏ]/i.test(c)) return locale === "ko" ? 1 : 0;
  if (/[0-9]/.test(c)) return 2;
  if (/[぀-ヿ一-鿿]/.test(c)) return 3;
  return 4;
}

/** 내 세대에 낯선 말: 세대가 정해져 있고 내 세대가 그 안에 없다 */
export const unfamiliarTo = (row: DictionaryRow, gen: string | null) =>
  !!gen && row.generations.length > 0 && !row.generations.includes("all") && !row.generations.includes(gen as Generation);

export function sortRows(rows: DictionaryRow[], sort: SortKey, locale: Locale, readerGen: string | null = null): DictionaryRow[] {
  const collators = new Map<string, Intl.Collator>();
  const coll = (lang: string) => {
    if (!collators.has(lang)) collators.set(lang, new Intl.Collator(lang === "zh" ? "zh-Hant" : lang));
    return collators.get(lang)!;
  };
  const byName = (a: DictionaryRow, b: DictionaryRow) => {
    const d = scriptRank(a.canonical, locale) - scriptRank(b.canonical, locale);
    // 같은 글자 갈래 안에서는 표제어 언어의 순서로(일본어 표제어가 한국 한자음 순으로 서던 것)
    return d || coll(a.lang === b.lang ? a.lang : locale).compare(a.canonical, b.canonical);
  };
  const desc = (x: string | null, y: string | null) => (y ?? "").localeCompare(x ?? "");
  const out = [...rows];
  if (sort === "used") return out.sort((a, b) => desc(a.last_used, b.last_used) || byName(a, b));
  if (sort === "changed") return out.sort((a, b) => desc(a.changed, b.changed) || byName(a, b));
  if (sort === "unfamiliar") return out.sort((a, b) => Number(unfamiliarTo(b, readerGen)) - Number(unfamiliarTo(a, readerGen)) || byName(a, b));
  return out.sort(byName);
}

export interface Filters { q: string; regions: string[]; kind: string; lang: string; risk: string }

/** 지역 외 조건으로 거른다(지역 칩의 건수와 '다른 지역에 n개' 를 세려고 따로 둔다). */
export function matchesExceptRegion(r: DictionaryRow, f: Filters): boolean {
  if (f.kind && r.category !== f.kind) return false;
  if (f.lang && r.lang !== f.lang) return false;
  if (f.risk && riskKey(r) !== f.risk) return false;
  const q = f.q.trim().toLowerCase();
  return !q || r.search.includes(q);
}

export const inRegions = (r: DictionaryRow, regions: string[]) => !regions.length || r.regions.some((x) => regions.includes(x));

/** 검색어가 표제어가 아니라 다른 표기로 걸렸으면 그 표기 — 표제어 아래에 '다른 표기: …' 로 한 줄 보인다. */
export function aliasHit(r: DictionaryRow, q: string): string | null {
  const s = q.trim().toLowerCase();
  if (!s || r.canonical.toLowerCase().includes(s)) return null;
  return r.aliases.find((a) => a.toLowerCase().includes(s)) ?? null;
}

export const PAGE_SIZE = 50;
