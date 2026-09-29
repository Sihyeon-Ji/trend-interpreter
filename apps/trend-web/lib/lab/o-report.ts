/* 디자인 초안 1 '트렌드 리포트형'(/lab/o-report)의 뷰 모델과 계산. 서버·브라우저 어디서나 쓰는 순수 함수만 둔다.
   숫자는 모두 네이버 데이터랩 연령대별 검색 곡선에서 나온다(한국 검색만). 곡선이 없거나 모자라면 null — 화면은 0 이나 가짜 선을 그리지 않고 말로 알린다.
   증감 규칙은 이 파일의 growthOf 하나다. 다른 화면·백엔드가 같은 숫자를 내려면 이 규칙을 옮겨 가면 된다(docs/트렌드/시안-o-report.md). */
import type { Locale } from "@/lib/i18n";
import type { Diffusion, Lifecycle } from "@/lib/contract/types";
import type { GenerationCurve } from "@/lib/trends/types";

export type Risk = "caution" | "avoid" | "unknown" | null;
export type RiskKey = "caution" | "avoid" | "unknown" | "none";
export type ListKey = "rising" | "fading" | "caution" | "watch";
export type SortKey = "base" | "gain";
export type Weeks = 4 | 12;

/** 쓸 때 조심의 이유 한 줄. quote 는 사전 뜻풀이의 주의점 원문(한국어) — 영어 화면에서 lang="ko" 로 붙인다 */
export interface RiskNote { text: string; quote?: string }

/** 표의 한 줄. 서버가 만들어 브라우저로 넘긴다 — 필요한 칸만. */
export interface Row {
  id: string;
  name: string;
  lang?: string;             // 원문 글자의 말 (HTML lang)
  reading: string | null;    // 읽기 도움 — 한글이 없는 표제어에 붙인 한글 표기(推し活 → 오시카츠). 한국어 화면만
  readingLang?: string;
  gloss: string;
  glossLang?: string;        // 영어 화면에 번역이 없어 한국어 뜻이 나갈 때 "ko"
  lifecycle: Lifecycle;
  diffusion: Diffusion | null;
  risk: Risk;
  riskNotes: RiskNote[];     // 쓸 때 조심 이유 — 커뮤니티 인용·사이트 이름을 뗀 쉬운 말, 알아본 것 전부 (riskNotesOf)
  regions: string[];
  growth: number | null;     // 최근 창 / 직전 창 − 1 (한국 검색, growthOf). 모자라면 null
  rank: number | null;       // '쓰이는 밈' 에서만, 검색이 늘어난 순. 셀 수 없으면 null
  rankChange: number | null; // 한 창 전 같은 방식으로 매긴 순위와 비교 (+ 오름). 비교할 수 없으면 null
  searched: boolean;         // 네이버 검색 곡선이 있나 (있어도 드문드문하면 증감·선이 없다)
  spark: number[] | null;    // 주 단위 검색 지수 (최대 26주) — 증감을 센 연령대의 평균
  sparkRecent: number;       // spark 끝에서 몇 주가 최근 창인지
  lastUsed: string | null;   // 고른 지역에서 가장 최근에 쓰인 때 (검색 자료가 없는 지역의 표·표지에 쓴다)
  thumb: Thumb | null;
}

export interface Thumb { src: string; href: string; title: string }

/** 오른쪽 미리보기(데스크톱)와 표지에 쓰는 사전 항목 요약. 첫 화면은 고른 밈 하나만 서버에서 넣고, 나머지는 누를 때 받는다 */
export interface Preview {
  id: string;
  aliases: string[];
  definition: string | null;
  origin: string | null;
  nuance: string | null;
  plain: string | null;
  textLang?: string;
  refs: SourceRef[];
  verified: boolean;
  media: Media | null;
}

export interface SourceRef { name: string; nameLang?: string; title: string; titleLang?: string; url: string; date: string; kind: "wiki" | "news" | "video" }
export interface Media { kind: "image" | "video"; src: string; href: string; title: string; license?: string; attribution?: string }

/** 표지(이번 주 주목)의 곡선 — 7일 평균을 몇 날씩 묶어 줄인 것. 끝에서 recent 개가 최근 창, 그 앞 base 개가 비교한 창 */
export interface Silhouette { values: number[]; recent: number; base: number }

/** 가장 많이 늘어난 연령대 — 표지가 표에 없는 것을 하나 더 말한다 */
export interface Driver { gen: string; label: string; change: number }

/** 최근 변화 한 줄 (브라우저에서 지난 방문 시각과 견준다) */
export interface Change {
  kind: "verified" | "meaning_changed" | "spike";
  at: string;
  id: string | null;
  label: string;
  lang?: string;
  region?: string | null;
  note: string | null;       // 새 밈: 뜻 한 줄, 뜻 바뀜: 이전 뜻, 급증: 이유
  noteLang?: string;
}

/* ───────── 검색 곡선 계산 ───────── */

const DAY = 86_400_000;
const toDay = (iso: string) => Math.floor(Date.parse(`${iso.slice(0, 10)}T00:00:00Z`) / DAY);
export const dayIso = (d: number) => new Date(d * DAY).toISOString().slice(0, 10);
const sum = (xs: number[]) => xs.reduce((a, b) => a + b, 0);

export const GEN_ORDER = ["10s", "20s", "30s", "40s", "50s+"];

/** 연령대 곡선들을 한 가로축(첫날–마지막 날)에 맞춘 것. 데이터랩은 검색이 없는 날을 빼고 주므로 빈 날은 0 이다. */
export interface Aligned { start: number; end: number; gens: { gen: string; values: number[]; peak: string | null }[] }

export function align(curves: GenerationCurve[]): Aligned | null {
  const series = curves.filter((c) => c.points.length > 0);
  if (!series.length) return null;
  let start = Infinity, end = -Infinity;
  for (const c of series) for (const [d] of c.points) { const x = toDay(d); if (x < start) start = x; if (x > end) end = x; }
  const gens = [...series]
    .sort((a, b) => GEN_ORDER.indexOf(a.generation) - GEN_ORDER.indexOf(b.generation))
    .map((c) => {
      const values = new Array<number>(end - start + 1).fill(0);
      for (const [d, v] of c.points) values[toDay(d) - start] = v;
      return { gen: c.generation, values, peak: c.peak_date };
    });
  return { start, end, gens };
}

/** 한 창에 검색이 있어야 하는 날 — 28일이면 20일, 84일이면 60일(같은 71%) */
export const minDays = (w: number) => Math.round((w * 20) / 28);
/** 셈에 넣을 연령대가 이만큼은 있어야 한다 — 한 연령대만으로 '연령대 평균' 이라 하지 않는다 */
export const MIN_GROUPS = 2;

export interface GenWindow { recent: number; base: number; daysRecent: number; daysBase: number }

/** 한 연령대의 두 창 — 끝에서 shift 일 앞을 기준으로 최근 w 일과 그 앞 w 일 */
export function genWindow(values: number[], w: number, shift = 0): GenWindow | null {
  const n = values.length - shift;
  if (n - 2 * w < 0) return null;
  const r = values.slice(n - w, n), b = values.slice(n - 2 * w, n - w);
  return { recent: sum(r), base: sum(b), daysRecent: r.filter((v) => v > 0).length, daysBase: b.filter((v) => v > 0).length };
}

export interface Growth { value: number | null; used: string[]; byGen: Record<string, number | null> }

/** 증감 = 자료가 넉넉한 연령대만 모은 최근 w 일 합 ÷ 직전 w 일 합 − 1.
 *  연령대마다 두 창 가운데 하나라도 검색이 있는 날이 minDays 에 못 미치면 뺀다 — 드문드문 검색된 연령대 하나가
 *  전체를 끌어올리지 않게(빅맥송 50대 이상: 직전 4주 9일 → 최근 23일, 이 연령대 때문에 +58% 로 보였다. 09-29 검토).
 *  남은 연령대가 MIN_GROUPS 보다 적으면 세지 않는다. 연령대마다 자기 최고점이 100 이라, 합은 곧 같은 무게의 평균이다. */
export function growthOf(a: Aligned, w: number, shift = 0): Growth {
  const byGen: Record<string, number | null> = {};
  const used: string[] = [];
  let R = 0, B = 0;
  for (const g of a.gens) {
    const x = genWindow(g.values, w, shift);
    const ok = !!x && x.daysRecent >= minDays(w) && x.daysBase >= minDays(w) && x.base > 0;
    byGen[g.gen] = ok && x ? x.recent / x.base - 1 : null;
    if (ok && x) { R += x.recent; B += x.base; used.push(g.gen); }
  }
  return { value: used.length >= MIN_GROUPS && B > 0 ? R / B - 1 : null, used, byGen };
}

/** 화면에 그리는 지수 — 증감을 센 연령대들의 평균(그림과 숫자가 같은 자료다). gens 가 비면 모든 연령대 */
export function indexOf(a: Aligned, gens?: string[]): number[] {
  const pick = gens?.length ? a.gens.filter((g) => gens.includes(g.gen)) : a.gens;
  const n = a.end - a.start + 1;
  const out = new Array<number>(n).fill(0);
  for (const g of pick) for (let i = 0; i < n; i++) out[i] += g.values[i] / pick.length;
  return out;
}

/** 가장 많이 늘어난 연령대 (셈에 넣은 연령대 가운데, 늘었을 때만) */
export function driverOf(g: Growth): { gen: string; change: number } | null {
  let best: { gen: string; change: number } | null = null;
  for (const gen of g.used) {
    const c = g.byGen[gen];
    if (c != null && c > 0 && (!best || c > best.change)) best = { gen, change: c };
  }
  return best;
}

/** 곡선의 마지막 날이 보드 시각보다 이만큼 오래되면 '최근' 이라고 말하지 않는다 */
const STALE_DAYS = 21;
export const isStale = (a: { end: number }, boardAt: string) => toDay(boardAt) - a.end > STALE_DAYS;

/** 주 단위로 묶은 지수 (끝에서부터 7일씩, 최대 26주) */
export function weekly(values: number[], maxWeeks = 26): number[] {
  const out: number[] = [];
  for (let end = values.length; end - 7 >= 0 && out.length < maxWeeks; end -= 7) out.unshift(sum(values.slice(end - 7, end)) / 7);
  return out;
}

/** 7일 이동 평균 */
export function movingAverage(values: number[], k = 7): number[] {
  return values.map((_, i) => { const from = Math.max(0, i - k + 1); return sum(values.slice(from, i + 1)) / (i + 1 - from); });
}

/** 표지용: 7일 이동 평균을 step 일마다 한 점으로. 끝에서 w 일, 그 앞 w 일이 몇 점인지도 함께 */
export function silhouette(values: number[], w: number, step = 2): Silhouette {
  const ma = movingAverage(values);
  const out: number[] = [];
  for (let i = ma.length - 1; i >= 0; i -= step) out.unshift(Math.round(ma[i] * 10) / 10);
  return { values: out, recent: Math.ceil(w / step), base: Math.ceil(w / step) };
}

/** 순위: 늘어난 정도가 있는 줄만 큰 순서로 1, 2, 3 … 순위 변화는 한 창 전 같은 방식의 순위와 비교(둘 다 셀 수 있을 때만). */
export function rankRows<T extends { id: string; growth: number | null; prevGrowth: number | null }>(rows: T[]) {
  const now = rows.filter((r) => r.growth != null).sort((a, b) => b.growth! - a.growth!);
  const before = rows.filter((r) => r.prevGrowth != null).sort((a, b) => b.prevGrowth! - a.prevGrowth!);
  const rankNow = new Map(now.map((r, i) => [r.id, i + 1]));
  const rankBefore = new Map(before.map((r, i) => [r.id, i + 1]));
  return rows.map((r) => {
    const rank = rankNow.get(r.id) ?? null;
    const prev = rankBefore.get(r.id);
    return { row: r, rank, rankChange: rank != null && prev != null ? prev - rank : null };
  });
}

/* ───────── 글자 ───────── */

const HANGUL = /[가-힯]/;
const NON_LATIN = /[^\u0000-ɏ\s\p{P}\p{S}\d]/u;
export const hasHangul = (s: string) => HANGUL.test(s);

/** 읽기 도움: 한국어 화면이면 한글이 없는 표제어에 한글 표기를, 영어 화면이면 라틴 글자가 아닌 표제어에 라틴 표기를 */
export function readingOf(name: string, aliases: string[], locale: Locale): string | null {
  if (locale === "ko") return HANGUL.test(name) ? null : aliases.find((a) => HANGUL.test(a) && a !== name) ?? null;
  return NON_LATIN.test(name) ? aliases.find((a) => !NON_LATIN.test(a) && a !== name) ?? null : null;
}

/* 쓸 때 조심의 이유. 백엔드 규칙이 남긴 문장에는 커뮤니티 글의 인용과 사이트 이름이 붙어 오는데(“…” (bsky.app)),
   커뮤니티 글은 쓰임을 재는 데만 쓰고 화면에 내지 않는다(09-29 사용자 결정) — 알아본 틀만 쉬운 말로 옮기고, 모르는 인용은 버린다.
   판정은 그대로다. 퍼센트는 쓰지 않는다: 규칙이 본 글이 5건만 넘어도 이유가 붙으므로 '40%' 가 다섯 건 가운데 둘일 수 있다(09-29 검토). */
const RISK_TEXT: Record<Locale, {
  byPerson: string; wordItself: string; badOrigin: string; sensitive: string; mostlyNegative: string; overHalfNegative: string; halfNegative: string; someNegative: string;
  dict: string; thin: string; none: string; clean: string;
}> = {
  ko: {
    byPerson: "사람이 직접 검토해 정한 수준이에요.",
    wordItself: "말 자체가 욕설이거나 성적인 표현이에요.",
    badOrigin: "비하·혐오에서 나온 말이라는 지적이 있어요.",
    sensitive: "민감한 맥락에서 쓰인 글이 {n}건 있어요.",
    mostlyNegative: "쓰인 글 대부분이 부정적인 맥락이었어요.",
    overHalfNegative: "쓰인 글의 절반 넘게 부정적인 맥락이었어요.",
    halfNegative: "쓰인 글의 절반쯤이 부정적인 맥락이었어요.",
    someNegative: "부정적인 맥락으로 쓰인 글이 적지 않았어요.",
    dict: "사전에 적힌 주의점: {q}",
    thin: "그 뜻으로 쓰인 글이 {n}건뿐이라 아직 판단하지 않았어요.",
    none: "그 뜻으로 쓰인 글을 아직 찾지 못해 판단하지 않았어요.",
    clean: "쓰인 글 {n}건에서 민감한 맥락을 찾지 못했어요.",
  },
  en: {
    byPerson: "A person reviewed this and set the level.",
    wordItself: "The word itself is a swear word or sexual.",
    badOrigin: "It is said to come from a slur or hate speech.",
    sensitive: "{n} uses appeared in sensitive contexts.",
    mostlyNegative: "Most of the uses we read were negative.",
    overHalfNegative: "More than half of the uses we read were negative.",
    halfNegative: "About half of the uses we read were negative.",
    someNegative: "A fair share of the uses we read were negative.",
    dict: "The dictionary entry warns:",
    thin: "Only {n} uses carry this meaning, so we haven't judged it yet.",
    none: "We haven't found this meaning in use yet, so it isn't judged.",
    clean: "No sensitive context in the {n} uses we read.",
  },
};

/** 알아본 이유 전부, 순서대로. 사전 주의점은 사전의 말 그대로(영어 화면은 한국어 원문을 quote 로) */
export function riskNotesOf(reasons: string[], locale: Locale): RiskNote[] {
  const T = RISK_TEXT[locale];
  const fill = (t: string, v: Record<string, string>) => t.replace(/\{(\w+)\}/g, (_, k: string) => v[k] ?? "");
  const out: RiskNote[] = [];
  for (const raw of reasons) {
    const r = raw.trim();
    let m: RegExpExecArray | null;
    if (r.startsWith("검수자가 정한 수준")) out.push({ text: T.byPerson });
    else if (r.startsWith("표제어 자체가 욕설")) out.push({ text: T.wordItself });
    else if (r.startsWith("영상 해석이 지적한 기원")) out.push({ text: T.badOrigin });
    else if ((m = /^위험 유형이 붙은 근거 (\d+)건/.exec(r))) out.push({ text: fill(T.sensitive, { n: m[1] }) });
    else if ((m = /^부정적으로 쓰인 근거가 (\d+)%/.exec(r))) {
      const p = Number(m[1]);
      out.push({ text: p >= 75 ? T.mostlyNegative : p >= 60 ? T.overHalfNegative : p >= 45 ? T.halfNegative : T.someNegative });
    } else if ((m = /^사전 뜻풀이에 적힌 주의점:\s*“([^”]+)”/.exec(r))) out.push(locale === "ko" ? { text: fill(T.dict, { q: m[1] }) } : { text: T.dict, quote: m[1] });
    else if ((m = /^그 뜻으로 쓰인 근거가 (\d+)건뿐/.exec(r))) out.push({ text: m[1] === "0" ? T.none : fill(T.thin, { n: m[1] }) });
    else if ((m = /^분류된 근거 (\d+)건에 위험 신호가 없다/.exec(r))) out.push({ text: fill(T.clean, { n: m[1] }) });
    // 모르는 문장: 인용이 들어 있으면 내지 않는다(누구의 글인지 알 수 없다). 인용이 없는 짧은 한국어 문장만 원문으로
    else if (locale === "ko" && !/[“”"「」]/.test(r) && !/\([\w.-]+\.[a-z]{2,}\)/i.test(r) && r.length < 120) out.push({ text: r });
  }
  return out.filter((x, i) => out.findIndex((y) => y.text === x.text && y.quote === x.quote) === i);
}

/* ───────── 이름 조판 — 표지와 항목 머리의 낱말을 칸 폭에 맞춘다 ─────────
   o-editorial 시안의 fitName 을 옮겨 왔다(09-29 검토: 길이 어림만으로 줄 수를 정해 긴 라틴 이름이 두 줄 예산을 넘겼다).
   줄은 서버에서 낱말 사이(띄어쓰기 없는 일본어·중국어·태국어는 Intl.Segmenter 조각 사이)에서 나누고,
   크기는 CSS 가 min(상한, 칸 폭 ÷ 가장 긴 줄의 폭, 칸 높이 ÷ 줄 수) 로 정한다. */

const WIDE = /[ᄀ-ᇿ㄰-㆏가-힣぀-ヿ㐀-鿿豈-﫿！-｠]/;
const THAI_MARK = /[ัิ-ฺ็-๎]/;
const NO_LINE_START = /^[、。，．・ー〜！？）」』】ぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮヵヶ]/;
const NO_LINE_END = /[（「『【〈《(]$/;
const ATTACH = /^([぀-ゟ]|[!?.,:;)\]]|ない|なく|ます|です|でした|ました|たい|じゃん|だよ|だね)$/;

function charEm(ch: string): number {
  if (WIDE.test(ch)) return 1;
  if (THAI_MARK.test(ch)) return 0;
  if (/[฀-๿]/.test(ch)) return 0.62;
  if (/\s/.test(ch)) return 0.28;
  if (/[A-Z]/.test(ch)) return 0.7;
  if (/[a-z]/.test(ch)) return /[ilj]/.test(ch) ? 0.28 : /[mw]/.test(ch) ? 0.86 : 0.56;
  if (/[0-9]/.test(ch)) return 0.6;
  return 0.36;
}

/* 글자 무리마다 실제 폭에 맞춘 배율 — Pretendard 800·자간 −0.04em 로 브라우저에서 잰 값(09-29):
   빅맥송 2.46em(어림 2.88), delulu 2.78em(2.56), Hongdae guy 5.92em(5.58), スキビディ 4.83em(4.80), ฟีลแฟน 3.11em(2.90).
   한글은 어림보다 좁고 라틴은 넓다 — 넘치지 않게 가장 넓게 잰 쪽에 여유를 조금 더 얹었다. */
const factor = (ch: string) => (/[가-힣ᄀ-ᇿ㄰-㆏]/.test(ch) ? 0.9 : /[぀-ヿ㐀-鿿豈-﫿！-｠]/.test(ch) ? 1.04 : /[฀-๿]/.test(ch) ? 1.1 : 1.12);

/** 굵은 글씨(800)에 자간을 좁혔을 때 한 줄의 대략 폭(em). 넘치지 않게 조금 넉넉히 잡는다 */
export function emWidth(s: string, tracking = -0.04): number {
  let w = 0;
  for (const ch of s) { const e = charEm(ch); if (e) w += (e + tracking) * factor(ch); }
  return w;
}

function splitWords(words: string[], k: number, joiner: string): string[][] {
  // 낱말 순서를 지키며 k 줄로 나누는 경우 가운데 가장 긴 줄이 가장 짧은 것, 같으면 줄 길이가 고른 것, 그다음 윗줄이 긴 것
  if (k === 1) return [words];
  let best: string[][] = [words];
  let bestKey = [Infinity, Infinity, Infinity];
  const rec = (start: number, left: number, acc: string[][]) => {
    if (left === 1) {
      const lines = [...acc, words.slice(start)];
      const ws = lines.map((ln) => emWidth(ln.join(joiner)));
      const mw = Math.max(...ws);
      const key = [mw, ws.reduce((a, w) => a + (mw - w) ** 2, 0), -ws[0]];
      const at = key.findIndex((v, i) => Math.abs(v - bestKey[i]) > 1e-6);
      if (at >= 0 && key[at] < bestKey[at]) { bestKey = key; best = lines; }
      return;
    }
    for (let i = start + 1; i <= words.length - (left - 1); i++) rec(i, left - 1, [...acc, words.slice(start, i)]);
  };
  rec(0, k, []);
  return best;
}

const segmenters: Record<string, Intl.Segmenter> = {};
function segments(s: string): string[] | null {
  const lang = /[぀-ヿ]/.test(s) ? "ja" : /[฀-๿]/.test(s) ? "th" : /[一-鿿]/.test(s) ? "zh" : null;
  if (!lang || typeof Intl.Segmenter !== "function") return null;
  segmenters[lang] ??= new Intl.Segmenter(lang, { granularity: "word" });
  const out: string[] = [];
  for (const { segment } of segmenters[lang].segment(s)) {
    if (out.length && (NO_LINE_START.test(segment) || ATTACH.test(segment) || NO_LINE_END.test(out[out.length - 1]))) out[out.length - 1] += segment;
    else out.push(segment);
  }
  return out.length > 1 ? out : null;
}

function charPieces(s: string): string[] {
  const out: string[] = [];
  for (const ch of s) {
    if (out.length && (NO_LINE_START.test(ch) || NO_LINE_END.test(out[out.length - 1]))) out[out.length - 1] += ch;
    else out.push(ch);
  }
  return out;
}

/** 이름을 줄로 나누고 가장 긴 줄의 폭(em)을 돌려준다. splitAbove = 그 칸이 상한 크기로 담는 대략의 폭(em). */
export function fitName(name: string, maxLines = 3, splitAbove = 4.6): { lines: string[]; em: number } {
  const clean = name.trim().replace(/\s+/g, " ");
  const one = emWidth(clean);
  if (one <= splitAbove || maxLines === 1) return { lines: [clean], em: Math.max(one, 1.2) };
  const spaced = clean.includes(" ");
  const pieces = spaced ? clean.split(" ") : segments(clean);
  const joiner = spaced ? " " : "";
  const chars = [...clean].length;
  const options: { lines: string[]; em: number }[] = [];
  for (let k = 2; k <= maxLines; k++) {
    const lines = pieces && pieces.length >= k
      ? splitWords(pieces, k, joiner).map((ln) => ln.join(joiner))
      : !spaced && chars > 6 && k <= Math.ceil(chars / 5) && WIDE.test(clean) ? splitWords(charPieces(clean), k, "").map((ln) => ln.join("")) : null;
    if (lines) options.push({ lines, em: Math.max(...lines.map((ln) => emWidth(ln))) });
  }
  // 고르는 값 = 상한에 견준 글자 크기 − 줄 하나 늘 때마다 0.12. 딱 맞는 줄 수에서 크기가 1% 모자라 한 줄을 더 쓰는 절벽을 없앤다
  // (Tung Tung Tung Sahur 가 'Tung Tung / Tung / Sahur' 로 셋이 되던 것)
  const value = (o: { lines: string[]; em: number }) => Math.min(1, splitAbove / o.em) - 0.12 * (o.lines.length - 1);
  const best = options.reduce((a, o) => (value(o) > value(a) + 1e-9 ? o : a), { lines: [clean], em: one });
  return { lines: best.lines, em: Math.max(best.em, 1.2) };
}

/* ───────── 찾기 — 프레임의 찾기 칸과 사전 화면이 같은 규칙을 쓴다 ───────── */

export const normQuery = (s: string) => s.toLowerCase().normalize("NFKC").replace(/[\s·・,.!?'"“”‘’~\-_/]+/g, "");

/** 낮을수록 가깝다. 99 = 맞지 않음 */
export function matchScore(item: { name: string; aliases: string[]; gloss: string }, q: string): number {
  const name = normQuery(item.name);
  if (name === q) return 0;
  if (name.startsWith(q)) return 1;
  if (name.includes(q)) return 2;
  if (item.aliases.some((a) => normQuery(a).includes(q))) return 3;
  if (normQuery(item.gloss).includes(q)) return 4;
  return 99;
}

/* ───────── 숫자·날짜 ───────── */

/** "+47%" / "−10%" / "0%" (빼기는 진짜 빼기표) */
export function fmtGrowth(g: number): string {
  const n = Math.round(g * 100);
  return `${n > 0 ? "+" : n < 0 ? "−" : ""}${Math.abs(n)}%`;
}
/** 삼각형 옆에 쓰는 크기만 — 방향은 ▲▼ 와 화면 읽기용 낱말이 맡는다 */
export const fmtPct = (g: number) => `${Math.abs(Math.round(g * 100))}%`;

const TZ: Record<Locale, string> = { ko: "Asia/Seoul", en: "UTC" };

/** "9월 29일" / "Sep 29" — 서버와 브라우저가 같은 값을 내도록 시간대를 고정한다. ref(기준 시각)와 해가 다르면 해를 붙인다 */
export function fmtDay(iso: string, locale: Locale, ref?: string | null): string {
  const d = new Date(iso.length <= 10 ? `${iso}T00:00:00Z` : iso);
  if (Number.isNaN(d.getTime())) return iso;
  const tz = iso.length <= 10 ? "UTC" : TZ[locale];
  const p = new Intl.DateTimeFormat("en-CA", { timeZone: tz, year: "numeric", month: "numeric", day: "numeric" }).formatToParts(d);
  const part = (t: string) => Number(p.find((x) => x.type === t)?.value);
  const withYear = !!ref && ref.slice(0, 4) !== String(part("year"));
  if (locale === "ko") return `${withYear ? `${part("year")}년 ` : ""}${part("month")}월 ${part("day")}일`;
  return new Intl.DateTimeFormat("en-US", { timeZone: tz, month: "short", day: "numeric", ...(withYear ? { year: "numeric" } : {}) }).format(d);
}

/** "9월 29일 13:25" / "Sep 29, 04:25 UTC" */
export function fmtTime(iso: string, locale: Locale): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const p = new Intl.DateTimeFormat("en-GB", { timeZone: TZ[locale], hour: "2-digit", minute: "2-digit", hour12: false }).format(d);
  return locale === "ko" ? `${fmtDay(iso, locale)} ${p}` : `${fmtDay(iso, locale)}, ${p} UTC`;
}
