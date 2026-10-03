/* 예시 데이터 모드의 카피 검사 — 백엔드 pipeline/copycheck.py 의 규칙을 예시 사전에 옮긴다. 뜻 검사(모델)는 하지 않는다(fit_source none).
   욕설 검사는 백엔드 match.unsafe 의 일부(예시용)만 본다. */
import { termPattern } from "../explain";
import type { CopyCheck, CopyIssue, CopyMeme } from "../types";
import { SAMPLE_RECORDS } from "./dictionary";
import { isFadingCard, sampleCards } from "./keyword-board";

const MAX_MEMES = 8;
// 백엔드 generate.REGION_LANG·_SCRIPT 와 같다 — 그 지역 말로 쓴 글에 넣을 수 있는 표기(로마자는 어디서나)
const REGION_LANG: Record<string, string> = { KR: "ko", JP: "ja", TW: "zh-Hant", HK: "zh-Hant", TH: "th", VN: "vi", ID: "id", PH: "en", MY: "ms", SG: "en" };
const SCRIPT: Record<string, RegExp> = { ko: /[가-힣]/u, ja: /[぀-ヿ一-鿿]/u, "zh-Hant": /[一-鿿]/u, th: /[฀-๿]/u };
const NON_LATIN = /[^\x00-\x7fÀ-ɏḀ-ỿ]/u;
const UNSAFE = /시발(?!점)|씨발|병신|fuck|shit(?![a-z])/iu;

const writable = (names: string[], region: string) => {
  const script = SCRIPT[REGION_LANG[region] ?? "en"];
  return names.some((n) => n && (!NON_LATIN.test(n) || (script && script.test(n))));
};

/** X 가 세는 글자 수 — 백엔드 generate.x_length 와 같다 */
export function xLength(text: string): number {
  let n = 0;
  for (const ch of text) {
    const o = ch.codePointAt(0) ?? 0;
    n += o <= 0x10ff || (o >= 0x2000 && o <= 0x200d) || (o >= 0x2010 && o <= 0x201f) || (o >= 0x2032 && o <= 0x2037) ? 1 : 2;
  }
  return n;
}

export function sampleCopyCheck(text: string, region: string): CopyCheck {
  const cards = new Map(sampleCards().map((c) => [c.term_id, c]));
  const hits: { at: number; matched: string; id: string; names: string[] }[] = [];
  for (const r of SAMPLE_RECORDS) {
    if (r.term.status !== "verified") continue;
    const names = [r.term.canonical, ...(r.term.aliases ?? [])];
    let best: { at: number; matched: string } | null = null;
    for (const n of names) {
      const m = termPattern(n).exec(text);
      if (m && (!best || m.index < best.at)) best = { at: m.index, matched: m[0] };
    }
    if (best) hits.push({ ...best, id: r.term.term_id, names });
  }
  hits.sort((a, b) => a.at - b.at);
  const memes: CopyMeme[] = [];
  for (const h of hits.slice(0, MAX_MEMES)) {
    const c = cards.get(h.id);
    if (!c) continue;
    const issues: CopyIssue[] = [];
    if (c.risk_level === "avoid") issues.push({ code: "avoid", note: "" });
    else if (c.risk_level === "caution") issues.push({ code: "caution", note: "비하·조롱·선정·정치 맥락으로 쓰지 말 것" });
    else if (!c.risk_level && c.risk_checked_at) issues.push({ code: "undecided", note: "" });
    if (isFadingCard(c)) issues.push({ code: "fading", note: "" });
    if (!c.regions.includes(region)) issues.push({ code: "not_in_region", note: "" });
    else if (!writable(h.names, region)) issues.push({ code: "no_script", note: "" });
    memes.push({ term_id: c.term_id, canonical: c.canonical, lang: c.lang, matched: h.matched, gloss_ko: c.gloss_ko, gloss_en: c.gloss_en,
      regions: c.regions, lifecycle: c.lifecycle, diffusion: c.diffusion ?? null, risk_level: c.risk_level ?? null,
      risk_checked_at: c.risk_checked_at ?? null, issues, fit: null, fit_note: null });
  }
  return { region, memes, unsafe: UNSAFE.test(text), x_length: xLength(text), fit_source: "none" };
}
