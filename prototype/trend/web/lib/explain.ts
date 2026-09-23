/* 메시지 해석: 사전에 있는 표현을 찾아 뜻·유래·뉘앙스를 사용자 언어로 엮는다. 규칙 기반.
   제품에서는 사전에 없는 표현이 나오면 자동 조사로 넘긴다. */
import { t, type Locale } from "./i18n";
import type { Reader } from "./reader";
import { L, joinGens, regionLabel } from "./labels";
import type { Meaning, MeaningText, TermRecord } from "./types";

export interface Explanation {
  record: TermRecord;
  matched: string;
  meaning: Meaning | null;
  text: MeaningText | null; // 사용자 언어로 된 뜻
  headline: string; // 뜻 한 줄
  background: string; // 유래 + 뉘앙스 + 누가 쓰나
}

export interface ExplainResult {
  greeting?: string;
  items: Explanation[];
  plain: string | null; // '쉽게 풀어 쓰면' — 로컬 모델이 사전 뜻을 참고해 다시 쓴 문장. 없으면 null (규칙 치환은 쓰지 않는다)
}

const escapeRe = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const hasHangul = (s: string) => /[\u1100-\u11ff\u3130-\u318f\uac00-\ud7af]/.test(s);

/** 용어 → 정규식.
 *  - 한국어: 부분 문자열 매칭(조사·어미가 붙어도 잡힘) + 띄어쓰기 변형 허용("원영적사고").
 *  - 영문·숫자·기타 문자: 단어 경계 필수("6-7" 이 "2026-7" 에 걸리지 않게), 대소문자 무시. */
export function termPattern(candidate: string): RegExp {
  const body = candidate.trim().split(/\s+/).map(escapeRe).join(hasHangul(candidate) ? "\\s*" : "\\s+");
  if (hasHangul(candidate)) return new RegExp(body, "iu");
  return new RegExp(`(?<![\\p{L}\\p{N}-])${body}(?![\\p{L}\\p{N}-])`, "iu");
}

export function currentMeaning(record: TermRecord): Meaning | null {
  const open = record.meanings.filter((m) => !m.valid_to);
  return open.at(-1) ?? record.meanings.at(-1) ?? null;
}

/** 현행 뜻을 사용자 언어로. 번역이 없으면 원문(한국어). */
export function textFor(record: TermRecord, locale: Locale): MeaningText | null {
  const m = currentMeaning(record);
  if (!m) return null;
  if (locale === "en" && record.en) return record.en;
  // 한국어 화면도 번역본을 쓴다. 일본어 표제어의 뜻이 일본어 그대로 나가던 문제(2026-09-16 사용자 지적).
  if (locale === "ko" && record.ko) return { ...record.ko, plain: record.ko.plain ?? record.plain ?? null };
  return { definition: m.definition, expansion: m.expansion ?? null, origin: m.origin, nuance: m.nuance, plain: record.plain };
}

export function headlineFor(text: MeaningText, locale: Locale) {
  if (!text.expansion) return text.definition;
  const blend = /\s\+\s|→/.test(text.expansion); // "Lucky + Vicky", "아리가토 고자이마스 → 아자스"
  if (locale === "ko") return blend ? `${text.expansion}에서 온 말입니다. ${text.definition}` : `'${text.expansion}'의 줄임말입니다. ${text.definition}`;
  return blend ? `From ${text.expansion}. ${text.definition}` : `Short for ${text.expansion}. ${text.definition}`;
}

export function backgroundFor(record: TermRecord, text: MeaningText, m: Meaning, locale: Locale, reader: Reader = {}) {
  const parts: string[] = [];
  if (text.origin && text.origin !== "unknown") parts.push(text.origin);
  if (text.nuance) parts.push(text.nuance);
  const lc = L(locale).lifecycleSentence[record.term.lifecycle ?? "unknown"];
  const all = m.generations.includes("all");
  const who = locale === "ko"
    ? all ? "세대를 가리지 않고 씁니다." : `주로 ${joinGens(locale, m.generations)}가 씁니다.`
    : all ? "Used across all ages." : `Mostly used by people in their ${joinGens(locale, m.generations)}.`;
  parts.push(lc ? `${who} ${lc}` : who);
  // 읽는 사람 기준 한 줄: 내 세대가 안 쓰는 말인가, 내 나라에서 안 쓰는 말인가
  if (reader.gen && !all && !m.generations.includes(reader.gen)) {
    const g = L(locale).generation[reader.gen];
    parts.push(locale === "ko" ? `${g} ${t(locale, "bg_unfamiliar_gen")}` : `${t(locale, "bg_unfamiliar_gen")} ${g}.`);
  }
  if (reader.region && m.regions.length && !m.regions.includes(reader.region) && !m.regions.includes("GLOBAL")) {
    const r = regionLabel(locale, reader.region);
    parts.push(locale === "ko" ? `${r}${t(locale, "bg_other_region")}` : `${t(locale, "bg_other_region")} ${r}.`);
  }
  return parts.join(" ");
}

export function explainMessage(text: string, records: TermRecord[], locale: Locale, plain: string | null = null, reader: Reader = {}): ExplainResult {
  const items: Explanation[] = [];
  for (const record of records) {
    const candidates = [record.term.canonical, ...(record.term.aliases ?? [])];
    const hit = candidates.find((c) => termPattern(c).test(text));
    if (!hit) continue;
    const meaning = currentMeaning(record);
    const mt = textFor(record, locale);
    items.push({
      record, matched: hit, meaning, text: mt,
      headline: mt ? headlineFor(mt, locale) : locale === "ko" ? "아직 뜻을 확인하는 중입니다." : "The meaning is still under review.",
      background: mt && meaning ? backgroundFor(record, mt, meaning, locale, reader) : "",
    });
  }
  const pos = (e: Explanation) => text.search(termPattern(e.matched));
  items.sort((a, b) => pos(a) - pos(b));
  const n = items.length;
  const greeting = reader.nick && n ? `${reader.nick}${t(locale, "home_greeting")} ${n}${t(locale, "home_greeting_unit")}` : undefined;
  return { items, plain: n ? plain : null, greeting };
}
