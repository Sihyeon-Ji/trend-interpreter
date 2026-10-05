/* 메시지 해석: 사전에 있는 표현을 찾아 뜻을 사용자 언어로 보인다. 규칙 기반.
   유래·뉘앙스·세대·단계는 문장으로 엮지 않고 화면이 라벨 행으로 나눈다 — 한 문단에 이으면 말투가 섞이고
   쓸 때 주의가 묻혔다(2026-09-29 검토). 제품에서는 사전에 없는 표현이 나오면 자동 조사로 넘긴다. */
import { termRegions } from "./dictionary/regions";
import { t, type Locale } from "./i18n";
import type { Reader } from "./reader";
import { L, regionLabel } from "./labels";
import type { Meaning, MeaningText, TermRecord } from "./types";

export interface Explanation {
  record: TermRecord;
  matched: string;
  meaning: Meaning | null;
  text: MeaningText | null; // 사용자 언어로 된 뜻
  headline: string; // 뜻 한 줄
  regions: string[]; // 주로 쓰는 지역 (대시보드와 같은 규칙)
  notes: string[]; // 읽는 사람 기준 안내: 내 세대가 안 쓰는 말인가, 내 나라에서 안 쓰는 말인가 (로그인했을 때만)
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
  // 한 글자 한글 표제어는 앞뒤에 다른 한글이 없을 때만 — '팀장님' 의 '님' 이 잡혔다(10-04, 백엔드 match.text_pattern 과 같다)
  const core = candidate.replace(/\s+/g, "");
  if (core.length === 1 && hasHangul(core)) return new RegExp(`(?<![가-힣])${escapeRe(core)}(?![가-힣])`, "u");
  const forms = predicateForms(candidate.trim());
  if (forms) return new RegExp(forms, "u");
  const body = candidate.trim().split(/\s+/).map(escapeRe).join(hasHangul(candidate) ? "\\s*" : "\\s+");
  if (hasHangul(candidate)) return new RegExp(body, "iu");
  return new RegExp(`(?<![\\p{L}\\p{N}-])${body}(?![\\p{L}\\p{N}-])`, "iu");
}

/** '-다' 로 실린 한 낱말 서술어 표제어의 활용형(찰지다 → 찰진·찰져, 마렵다 → 마려운, 폭룡적이다 → 폭룡적인)까지 찾는 정규식 본문.
 *  백엔드 match.predicate_forms 와 같다(10-05). '-니다' 꼴과 명사 + '이다' 는 그대로 둔다. 해당하지 않으면 null. */
export function predicateForms(word: string): string | null {
  if (!/^[가-힣]{2,}다$/u.test(word) || word.endsWith("니다")) return null;
  const stem = word.slice(0, -1);
  const prefix = stem.slice(0, -1), last = stem.slice(-1);
  if (last === "이" && !prefix.endsWith("적")) return null;
  const code = last.charCodeAt(0) - 0xac00;
  const cho = Math.floor(code / 588), jung = Math.floor((code % 588) / 28), jong = code % 28;
  const syl = (j: number, t: number) => String.fromCharCode(0xac00 + cho * 588 + j * 28 + t);
  if (jong === 0) {
    const forms = new Set([0, 4, 8, 16, 17].map((t) => syl(jung, t)));
    if ([0, 1, 4, 5].includes(jung) && last !== "하") forms.add(syl(jung, 20));
    const short = last === "하" ? 1 : ({ 20: 6, 18: 4, 13: 14, 8: 9 } as Record<number, number>)[jung];
    if (short !== undefined) { forms.add(syl(short, 0)); forms.add(syl(short, 20)); }
    return `${escapeRe(prefix)}(?:${[...forms].sort().join("|")})[가-힣]*`;
  }
  if (jong === 17) return `${escapeRe(prefix)}(?:${last}|${syl(jung, 0)}(?=[우워운울]))[가-힣]*`;   // ㅂ 불규칙
  return `${escapeRe(stem)}[가-힣]*`;   // 찾은 말은 어미까지 – 화면 인용이 '열받' 에서 끊기지 않게
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
  // 사전 뜻과 같은 말투로(명사형). '…입니다.' 를 붙이면 뒤따르는 뜻 문장과 말투가 섞였다
  if (locale === "ko") return blend ? `${text.expansion}에서 온 말. ${text.definition}` : `'${text.expansion}'의 줄임말. ${text.definition}`;
  return blend ? `From ${text.expansion}. ${text.definition}` : `Short for ${text.expansion}. ${text.definition}`;
}

/** 읽는 사람 기준 안내. 로그인해 세대·나라를 정한 사람에게만 나온다. */
export function readerNotes(m: Meaning, regions: string[], locale: Locale, reader: Reader = {}): string[] {
  const out: string[] = [];
  if (reader.gen && m.generations.length && !m.generations.includes("all") && !m.generations.includes(reader.gen)) {
    const g = L(locale).generation[reader.gen];
    out.push(locale === "ko" ? `${g} ${t(locale, "bg_unfamiliar_gen")}` : `${t(locale, "bg_unfamiliar_gen")} ${g}.`);
  }
  const where = new Set([...m.regions, ...regions]);
  if (reader.region && where.size && !where.has(reader.region) && !where.has("GLOBAL")) {
    const r = regionLabel(locale, reader.region);
    out.push(locale === "ko" ? `${r}${t(locale, "bg_other_region")}` : `${t(locale, "bg_other_region")} ${r}.`);
  }
  return out;
}

export function explainMessage(text: string, records: TermRecord[], locale: Locale, plain: string | null = null, reader: Reader = {}): ExplainResult {
  const items: Explanation[] = [];
  for (const record of records) {
    const candidates = [record.term.canonical, ...(record.term.aliases ?? [])];
    const hit = candidates.find((c) => termPattern(c).test(text));
    if (!hit) continue;
    const meaning = currentMeaning(record);
    const mt = textFor(record, locale);
    const regions = termRegions(record);
    items.push({
      record, matched: hit, meaning, text: mt, regions,
      headline: mt ? headlineFor(mt, locale) : t(locale, "dict_pending"),
      notes: meaning ? readerNotes(meaning, regions, locale, reader) : [],
    });
  }
  const pos = (e: Explanation) => text.search(termPattern(e.matched));
  items.sort((a, b) => pos(a) - pos(b));
  const n = items.length;
  const greeting = reader.nick && n ? `${reader.nick}${t(locale, "home_greeting")} ${n}${t(locale, "home_greeting_unit")}` : undefined;
  return { items, plain: n ? plain : null, greeting };
}
