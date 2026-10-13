/* 사전 색인의 행 모델과 거르기·정렬. 서버가 사전 기록(TermRecord)을 행 하나에 필요한 칸만 남겨 넘긴다 —
   기록 전체(근거·주간 수·뜻 버전)를 브라우저로 보내면 운영 데이터 148개에 2.26MB 였다(2026-09-29 검토). */
import type { Diffusion, RiskLevel } from "../contract/types";
import { currentMeaning, jaUntranslated, textFor } from "../explain";
import type { Locale } from "../i18n";
import type { Category, Generation, Lifecycle, TermRecord } from "../types";
import { localWord } from "../lang";
import { lastUsedOf, measuredUsage, termRegions } from "./regions";

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
  alt: string | null;            // 보이는 뜻과 다른 원문 뜻(영어 화면에서 번역된 말의 한국어 원문) — 검색에만 쓴다
  reading: string | null;        // 화면 언어로 쓴 표제어 읽기(TermRecord.readings) — 원문 곁에 작게, 검색에도(일본어 화면에서 「チャン」으로 장원영)
  name: string | null;           // 화면 언어의 원어 이름(TermRecord.names) — 있으면 표제어 대신 보이고 읽기는 붙이지 않는다(규동 → 牛丼)
}

export function toRow(r: TermRecord, locale: Locale): DictionaryRow {
  const shown = localWord({ ...r.term, names: r.names }, locale);
  const m = currentMeaning(r);
  const { expansion, definition } = glossParts(r, locale);
  const translated = locale === "en" ? !!r.en : locale === "ja" ? !jaUntranslated(r) : !!r.ko || (r.term.lang ?? "ko") === "ko";
  return {
    term_id: r.term.term_id, canonical: r.term.canonical, lang: r.term.lang ?? "ko", aliases: r.term.aliases ?? [],
    expansion, definition, meaning_lang: translated ? null : "ko",
    category: r.category, diffusion: r.term.diffusion ?? null, lifecycle: r.term.lifecycle ?? "unknown",
    // 정렬·'검사했나'에만 쓰는 시각은 날짜까지만 — 행마다 마이크로초까지 실려 나갔다
    regions: termRegions(r), last_used: lastUsedOf(r), changed: m?.valid_from?.slice(0, 10) ?? null,
    risk_level: r.term.risk_level ?? null, risk_checked_at: r.term.risk_checked_at?.slice(0, 10) ?? null,
    generations: [...new Set(measuredUsage(r.usage).map((u) => u.segment.generation))],
    alt: m?.definition && m.definition !== definition ? m.definition : null,
    // 화면 언어 이름이면 읽기는 붙이지 않고, 다른 나라 원어(goblin mode·牛丼)를 세울 때는 화면 언어 글자의 읽기를 곁에
    reading: shown.local && shown.lang === locale ? null : r.readings?.[locale] ?? null,
    name: shown.local ? shown.text : null,
  };
}

/* 브라우저로 넘길 때는 행을 칸 이름 없는 배열로 줄인다. 1만 1천여 행마다 칸 이름 16개가 이스케이프된 채 되풀이돼
   사전 첫 화면 HTML 이 5MB(gzip 1MB)였다(10-05). 칸 순서는 ROW_KEYS 하나로 정해 서버·브라우저가 같이 쓴다. */
const ROW_KEYS = [
  "term_id", "canonical", "lang", "aliases", "expansion", "definition", "meaning_lang", "category", "diffusion", "lifecycle",
  "regions", "last_used", "changed", "risk_level", "risk_checked_at", "generations", "alt", "reading", "name",
] as const satisfies ReadonlyArray<keyof DictionaryRow>;
// 칸을 하나 더하고 ROW_KEYS 에 빠뜨리면 여기서 형 검사가 실패한다(브라우저에서 그 칸이 조용히 비지 않게)
const allKeys: Record<Exclude<keyof DictionaryRow, (typeof ROW_KEYS)[number]>, never> = {};
void allKeys;
export type PackedRows = unknown[][];

export function packRows(rows: DictionaryRow[]): PackedRows {
  return rows.map((r) => ROW_KEYS.map((k) => r[k]));
}

export function unpackRows(packed: PackedRows): DictionaryRow[] {
  return packed.map((v) => Object.fromEntries(ROW_KEYS.map((k, i) => [k, v[i]])) as unknown as DictionaryRow);
}

export function riskKey(r: Pick<DictionaryRow, "risk_level" | "risk_checked_at">): RiskFilter {
  if (r.risk_level === "caution" || r.risk_level === "avoid" || r.risk_level === "none") return r.risk_level;
  return r.risk_checked_at ? "unknown" : "unchecked";
}

/** 가나다순에서 글자 갈래의 순서: 화면 언어의 글자가 먼저, 일본어·태국어 같은 다른 글자는 뒤에 모인다.
 *  일본어 화면은 가나·한자 → 라틴 → 숫자 → 한글 순. */
function scriptRank(s: string, locale: Locale): number {
  const c = s.trim().charAt(0);
  if (locale === "ja") {
    if (/[぀-ヿ一-鿿]/.test(c)) return 0;
    if (/[a-zÀ-ɏ]/i.test(c)) return 1;
    if (/[0-9]/.test(c)) return 2;
    if (/[가-힣ㄱ-ㅎ]/.test(c)) return 3;
    return 4;
  }
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
  return !q || searchText(r).includes(q);
}

// 검색 문자열은 브라우저에서 처음 찾을 때 만든다 — 행마다 뜻을 한 번 더 이어 보내 사전 첫 화면이 8.5MB 였다(10-04)
const searchCache = new WeakMap<DictionaryRow, string>();
function searchText(r: DictionaryRow): string {
  let s = searchCache.get(r);
  if (s === undefined) {
    s = [r.canonical, r.name ?? "", ...r.aliases, r.reading ?? "", r.expansion ?? "", r.definition ?? "", r.alt ?? ""].join(" ").toLowerCase();
    searchCache.set(r, s);
  }
  return s;
}

export const inRegions = (r: DictionaryRow, regions: string[]) => !regions.length || r.regions.some((x) => regions.includes(x));

/** 검색어가 표제어가 아니라 다른 표기로 걸렸으면 그 표기 — 표제어 아래에 '다른 표기: …' 로 한 줄 보인다. */
export function aliasHit(r: DictionaryRow, q: string): string | null {
  const s = q.trim().toLowerCase();
  if (!s || r.canonical.toLowerCase().includes(s)) return null;
  return r.aliases.find((a) => a.toLowerCase().includes(s)) ?? null;
}

export const PAGE_SIZE = 50;
