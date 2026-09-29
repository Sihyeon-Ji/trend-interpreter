/* 디자인 초안 1 '트렌드 리포트형'(/lab/o-report)의 뷰 모델과 계산. 서버·브라우저 어디서나 쓰는 순수 함수만 둔다.
   숫자는 모두 네이버 데이터랩 연령대별 검색 곡선에서 나온다(한국 검색만). 곡선이 없거나 모자라면 null — 화면은 0 이나 가짜 선을 그리지 않고 말로 알린다. */
import type { Locale } from "@/lib/i18n";
import type { Diffusion, Lifecycle } from "@/lib/contract/types";
import type { GenerationCurve } from "@/lib/trends/types";

export type Risk = "caution" | "avoid" | "unknown" | null;
export type ListKey = "rising" | "fading" | "caution" | "watch";
export type Weeks = 4 | 12;

/** 표의 한 줄. 서버가 만들어 브라우저로 넘긴다 — 필요한 칸만. */
export interface Row {
  id: string;
  name: string;
  lang?: string;             // 원문 글자의 말 (HTML lang)
  reading: string | null;    // 읽기 도움 — 화면 글자와 다른 글자의 표제어에 붙인 다른 표기(推し活 → 오시카츠)
  readingLang?: string;
  gloss: string;
  glossLang?: string;        // 영어 화면에 번역이 없어 한국어 뜻이 나갈 때 "ko"
  lifecycle: Lifecycle;
  diffusion: Diffusion | null;
  risk: Risk;
  riskNote: string | null;   // 쓸 때 조심 이유 한 줄 — 커뮤니티 인용·사이트 이름을 뗀 쉬운 말 (riskNoteOf)
  regions: string[];
  growth: number | null;     // 최근 창 / 직전 창 − 1 (한국 검색). 모자라면 null
  rank: number | null;       // '뜨는 밈' 에서만, 검색이 늘어난 순. 셀 수 없으면 null
  rankChange: number | null; // 한 창 전 같은 방식으로 매긴 순위와 비교 (+ 오름). 비교할 수 없으면 null
  spark: number[] | null;    // 주 단위 검색 지수 (최대 26주)
  sparkRecent: number;       // spark 끝에서 몇 주가 최근 창인지
  lastUsed: string | null;   // 고른 지역에서 가장 최근에 쓰인 때 (검색 자료가 없는 지역의 표·표지에 쓴다)
  thumb: Thumb | null;
}

export interface Thumb { src: string; href: string; title: string }

/** 오른쪽 미리보기(데스크톱)와 표지에 쓰는 사전 항목 요약 */
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

export interface SourceRef { name: string; title: string; url: string; date: string; kind: "wiki" | "news" | "video" }
export interface Media { kind: "image" | "video"; src: string; href: string; title: string; license?: string; attribution?: string }

/** 표지(이번 주 주목)의 곡선 — 7일 평균을 몇 날씩 묶어 줄인 것. 끝에서 recent 개가 최근 창, 그 앞 base 개가 비교한 창 */
export interface Silhouette { values: number[]; recent: number; base: number }

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

export interface DailyIndex { start: number; end: number; values: number[] }

/** 연령대 곡선들 → 하루 단위 지수 하나. 연령대마다 자기 최고점이 100 이라 크기를 서로 비교할 수 없으므로 같은 무게로 평균한다.
 *  데이터랩은 검색이 없는 날을 빼고 주므로 빈 날은 0 으로 채운다. */
export function dailyIndex(curves: GenerationCurve[]): DailyIndex | null {
  const series = curves.filter((c) => c.points.length > 0);
  if (!series.length) return null;
  let start = Infinity, end = -Infinity;
  for (const c of series) for (const [d] of c.points) { const x = toDay(d); if (x < start) start = x; if (x > end) end = x; }
  const values = new Array<number>(end - start + 1).fill(0);
  for (const c of series) for (const [d, v] of c.points) values[toDay(d) - start] += v / series.length;
  return { start, end, values };
}

const sum = (xs: number[]) => xs.reduce((a, b) => a + b, 0);

/** 끝에서 shift 일 앞을 기준으로 최근 w 일과 그 앞 w 일을 비교한다. 두 창을 합친 날의 70% 이상에 검색이 있어야 센다
 *  (드문드문 검색된 말은 몇 번의 검색으로 +1000% 가 나온다 — 뻘글 +1462%, 2026-09-29 실측). */
export function windowGrowth(idx: DailyIndex, w: number, shift = 0): number | null {
  const n = idx.values.length - shift;
  if (n - 2 * w < 0) return null;
  const win = idx.values.slice(n - 2 * w, n);
  if (win.filter((v) => v > 0).length < 0.7 * 2 * w) return null;
  const recent = sum(win.slice(w)), base = sum(win.slice(0, w));
  return base > 0 ? recent / base - 1 : null;
}

/** 곡선의 마지막 날이 보드 시각보다 이만큼 오래되면 '최근' 이라고 말하지 않는다 */
const STALE_DAYS = 21;
export const isStale = (idx: DailyIndex, boardAt: string) => toDay(boardAt) - idx.end > STALE_DAYS;

/** 주 단위로 묶은 지수 (끝에서부터 7일씩, 최대 26주) */
export function weekly(idx: DailyIndex, maxWeeks = 26): number[] {
  const out: number[] = [];
  for (let end = idx.values.length; end - 7 >= 0 && out.length < maxWeeks; end -= 7) out.unshift(sum(idx.values.slice(end - 7, end)) / 7);
  return out;
}

/** 표지용: 7일 이동 평균을 step 일마다 한 점으로. 끝에서 w 일, 그 앞 w 일이 몇 점인지도 함께 */
export function silhouette(idx: DailyIndex, w: number, step = 2): Silhouette {
  const ma = idx.values.map((_, i) => { const from = Math.max(0, i - 6); return sum(idx.values.slice(from, i + 1)) / (i + 1 - from); });
  const values: number[] = [];
  for (let i = ma.length - 1; i >= 0; i -= step) values.unshift(Math.round(ma[i] * 10) / 10);
  return { values, recent: Math.ceil(w / step), base: Math.ceil(w / step) };
}

/** 7일 이동 평균 (항목 화면의 큰 그림) */
export function movingAverage(values: number[], k = 7): number[] {
  return values.map((_, i) => { const from = Math.max(0, i - k + 1); return sum(values.slice(from, i + 1)) / (i + 1 - from); });
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

const HANGUL = /[\uac00-\ud7af]/;
const NON_LATIN = /[^\u0000-\u024f\s\p{P}\p{S}\d]/u;

/** 읽기 도움: 한국어 화면이면 한글이 없는 표제어에 한글 표기를, 영어 화면이면 라틴 글자가 아닌 표제어에 라틴 표기를 */
export function readingOf(name: string, aliases: string[], locale: Locale): string | null {
  if (locale === "ko") return HANGUL.test(name) ? null : aliases.find((a) => HANGUL.test(a) && a !== name) ?? null;
  return NON_LATIN.test(name) ? aliases.find((a) => !NON_LATIN.test(a) && a !== name) ?? null : null;
}

/* 쓸 때 조심의 이유 한 줄. 백엔드 규칙이 남긴 문장에는 커뮤니티 글의 인용과 사이트 이름이 붙어 오는데(“…” (bsky.app)),
   커뮤니티 글은 쓰임을 재는 데만 쓰고 화면에 내지 않는다(09-29 사용자 결정) — 수만 남겨 쉬운 말로 옮긴다. 판정은 그대로다. */
const RISK_TEXT: Record<Locale, { sensitive: string; negative: string; dict: string; thin: string; none: string; clean: string }> = {
  ko: {
    sensitive: "민감한 맥락에서 쓰인 글이 {n}건 있어요.",
    negative: "쓰인 글의 {n}%가 부정적이었어요.",
    dict: "사전에 적힌 주의점: {q}",
    thin: "그 뜻으로 쓰인 글이 {n}건뿐이라 아직 판단하지 않았어요.",
    none: "그 뜻으로 쓰인 글을 아직 찾지 못해 판단하지 않았어요.",
    clean: "쓰인 글 {n}건에서 민감한 맥락을 찾지 못했어요.",
  },
  en: {
    sensitive: "{n} uses appeared in sensitive contexts.",
    negative: "{n}% of the uses we read were negative.",
    dict: "The dictionary entry flags a caution.",
    thin: "Only {n} uses carry this meaning, so we haven't judged it yet.",
    none: "We haven't found this meaning in use yet, so it isn't judged.",
    clean: "No sensitive context in the {n} uses we read.",
  },
};

export function riskNoteOf(reasons: string[], locale: Locale): { text: string; lang?: string } | null {
  const T = RISK_TEXT[locale];
  const fill = (t: string, v: Record<string, string>) => t.replace(/\{(\w+)\}/g, (_, k: string) => v[k] ?? "");
  for (const raw of reasons) {
    const r = raw.trim();
    let m = /^위험 유형이 붙은 근거 (\d+)건/.exec(r);
    if (m) return { text: fill(T.sensitive, { n: m[1] }) };
    m = /^부정적으로 쓰인 근거가 (\d+)%/.exec(r);
    if (m) return { text: fill(T.negative, { n: m[1] }) };
    m = /^사전 뜻풀이에 적힌 주의점:\s*“([^”]+)”/.exec(r);
    if (m) return locale === "ko" ? { text: fill(T.dict, { q: m[1] }) } : { text: T.dict };
    m = /^그 뜻으로 쓰인 근거가 (\d+)건뿐/.exec(r);
    if (m) return { text: m[1] === "0" ? T.none : fill(T.thin, { n: m[1] }) };
    m = /^분류된 근거 (\d+)건에 위험 신호가 없다/.exec(r);
    if (m) return { text: fill(T.clean, { n: m[1] }) };
    // 모르는 문장: 인용이 들어 있으면 내지 않는다(누구의 글인지 알 수 없다). 인용이 없는 한국어 문장만 원문으로
    if (!/[“”"「」]/.test(r) && !/\([\w.-]+\.[a-z]{2,}\)/i.test(r) && r.length < 120) return locale === "ko" ? { text: r } : null;
  }
  return null;
}

/** 표지 글자 크기를 정하는 '보이는 길이' — 한글·한자·가나는 1, 라틴 소문자는 0.56 … */
export function visualLength(text: string): number {
  let n = 0;
  for (const ch of text) {
    if (/[\u1100-\u11ff\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af\uff00-\uffef]/.test(ch)) n += 1;
    else if (/[\u0e00-\u0e7f]/.test(ch)) n += 0.62;
    else if (/\s/.test(ch)) n += 0.3;
    else if (/[A-Z]/.test(ch)) n += 0.68;
    else n += 0.56;
  }
  return Math.max(1, n);
}

export const fmtGrowth = (g: number) => `${g >= 0 ? "+" : "−"}${Math.abs(Math.round(g * 100))}%`;
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

/** "2026.09.15" — 기록·출처 칸 */
export const fmtDate = (iso: string) => iso.slice(0, 10).replace(/-/g, ".");
