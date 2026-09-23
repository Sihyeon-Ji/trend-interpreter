/* 위키식 색인: 첫 글자 기준(한글 초성 ㄱ~ㅎ, 로마자 A~Z, 숫자, 그 밖의 문자). */
import type { Locale } from "../i18n";
import type { TermRecord } from "../types";

const CHO = ["ㄱ", "ㄲ", "ㄴ", "ㄷ", "ㄸ", "ㄹ", "ㅁ", "ㅂ", "ㅃ", "ㅅ", "ㅆ", "ㅇ", "ㅈ", "ㅉ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"];
const BASE: Record<string, string> = { ㄲ: "ㄱ", ㄸ: "ㄷ", ㅃ: "ㅂ", ㅆ: "ㅅ", ㅉ: "ㅈ" };
export const KO_INITIALS = ["ㄱ", "ㄴ", "ㄷ", "ㄹ", "ㅁ", "ㅂ", "ㅅ", "ㅇ", "ㅈ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"];
export const LATIN = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("");
export const DIGITS = "0-9";
export const OTHER = "#";

export function initialOf(term: string): string {
  const ch = term.trim().charAt(0);
  if (!ch) return OTHER;
  const code = ch.charCodeAt(0);
  if (code >= 0xac00 && code <= 0xd7a3) {
    const cho = CHO[Math.floor((code - 0xac00) / 588)];
    return BASE[cho] ?? cho;
  }
  if (/[a-z]/i.test(ch)) return ch.toUpperCase();
  if (/[0-9]/.test(ch)) return DIGITS;
  return OTHER;
}

export interface InitialGroup { key: string; items: TermRecord[] }

/** 화면 언어의 문자를 먼저: 한국어 화면은 ㄱ~ㅎ → A~Z → 0-9 → #, 영어 화면은 A~Z → ㄱ~ㅎ → 0-9 → # */
export function groupByInitial(records: TermRecord[], locale: Locale): InitialGroup[] {
  const order = locale === "ko" ? [...KO_INITIALS, ...LATIN, DIGITS, OTHER] : [...LATIN, ...KO_INITIALS, DIGITS, OTHER];
  const map = new Map<string, TermRecord[]>();
  for (const r of records) {
    const k = initialOf(r.term.canonical);
    map.set(k, [...(map.get(k) ?? []), r]);
  }
  return order.filter((k) => map.has(k)).map((k) => ({ key: k, items: map.get(k)!.sort((a, b) => a.term.canonical.localeCompare(b.term.canonical, locale)) }));
}
