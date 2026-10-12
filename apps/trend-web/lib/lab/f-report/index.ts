/* 시안 f-report(트렌드 리포트형)의 자료 가공. 화면이 쓰는 값은 전부 여기서 계산한다 — 숫자를 지어내지 않고, 자료가 없으면 null.
   - 쓰임 추이·증감: 네이버 데이터랩 나이대별 검색 관심(GET /terms/{id}/generations)만 쓴다. 나이대마다 자기 최고점이 100 인 상대값이라
     표제어끼리 높이를 견줄 수 없다 → 순위 변동(▲2)은 만들지 않고, 같은 표제어 안에서 '최근 28일 대 그 전 28일' 증감만 낸다.
     증감 규칙은 한 곳(combineCurves)뿐이다 — 타일·행·미리보기·항목이 같은 숫자를 낸다.
   - 근거: 커뮤니티·SNS 글은 제목·인용·사이트 이름을 화면에 내지 않는다(2026-09-29 자료 방침). 백엔드가 news 로 붙인 커뮤니티(Weverse·브런치·네이버 블로그)도 같다.
     보이는 출처는 참고 위키·기사·영상뿐이고, 글로 가지 않는 첫 화면 주소(https://youtube.com/)는 근거처럼 보이지 않게 뺀다. */
import type { LabLocale as Locale } from "@/lib/i18n";
import type { KeywordCard, KeywordList } from "@/lib/types";
import type { GenerationCurve, UpdateItem } from "@/lib/trends/types";

export const GEN_ORDER = ["10s", "20s", "30s", "40s", "50s+"];
export const WINDOW_DAYS = 28;   // 비교 창: 최근 28일 대 그 전 28일, 달력 날짜로
export const MIN_DAYS = 20;      // 창마다 검색이 있던 날이 이만큼은 있어야 그 나이대를 센다 (드문 검색어는 몇 번의 검색으로 +1000% 가 났다)
export const STALE_DAYS = 21;    // 곡선 끝이 갱신 시각보다 이만큼 오래되면 '최근' 이라 말하지 않는다
export const SPARK_WEEKS = 26;

const DAY = 86_400_000;
const toDay = (iso: string) => Math.floor(Date.parse(`${iso.slice(0, 10)}T00:00:00Z`) / DAY);
export const dayIso = (d: number) => new Date(d * DAY).toISOString().slice(0, 10);
const sum = (xs: number[]) => xs.reduce((a, b) => a + b, 0);
const mean = (xs: number[]) => (xs.length ? sum(xs) / xs.length : 0);
const r1 = (v: number) => Math.round(v * 10) / 10;

/** 하루 단위 격자. 데이터랩은 검색이 없는 날을 빼고 주므로 빈 날은 0 이다. */
interface Grid { start: number; end: number; values: number[] }

function gridOf(points: [string, number][], start: number, end: number): Grid {
  const values = new Array<number>(end - start + 1).fill(0);
  for (const [d, v] of points) {
    const x = toDay(d);
    if (!Number.isNaN(x) && x >= start && x <= end) values[x - start] += v;
  }
  return { start, end, values };
}

/** 끝 w 일과 그 앞 w 일. 격자가 두 창보다 짧으면 null */
function windows(g: Grid, w = WINDOW_DAYS): { recent: number[]; base: number[] } | null {
  const n = g.values.length;
  if (n < 2 * w) return null;
  return { recent: g.values.slice(n - w), base: g.values.slice(n - 2 * w, n - w) };
}
const searchedDays = (xs: number[]) => xs.filter((v) => v > 0).length;

/** 한 창의 합을 그 앞 창의 합과 견준 정수 %. 창마다 검색이 있던 날이 MIN_DAYS 미만이면 null(자료 부족). */
function growthOf(g: Grid): number | null {
  const w = windows(g);
  if (!w || searchedDays(w.recent) < MIN_DAYS || searchedDays(w.base) < MIN_DAYS) return null;
  const a = sum(w.recent), b = sum(w.base);
  return b > 0 ? Math.round((a / b - 1) * 100) : null;
}

/** 7일 이동 평균(끝 기준) */
function movingAverage(values: number[], k = 7): number[] {
  return values.map((_, i) => { const from = Math.max(0, i - k + 1); return r1(mean(values.slice(from, i + 1))); });
}

/** 끝에서부터 7일씩 묶은 주 평균, 오래된 주가 앞 */
function weekly(values: number[], weeks = SPARK_WEEKS): number[] {
  const out: number[] = [];
  for (let end = values.length; end - 7 >= 0 && out.length < weeks; end -= 7) out.unshift(r1(mean(values.slice(end - 7, end))));
  return out;
}

export interface GenTrend { generation: string; spark: number[]; peak: string | null; pct: number | null; counted: boolean }
export interface Trend {
  pct: number | null;          // 최근 28일 대 그 전 28일, 정수 %. 셀 수 있는 나이대가 없거나 곡선이 오래됐으면 null
  counted: number;             // 셈에 든 나이대 수
  stale: boolean;              // 곡선 끝이 갱신 시각보다 STALE_DAYS 넘게 오래됨
  daily: number[];             // 셈에 든 나이대의 평균(없으면 전체), 날짜순 — 그림용
  smooth: number[];            // 7일 이동 평균 — 큰 곡선용(날 것은 톱니처럼 보였다)
  recentDays: number;          // smooth 끝에서 최근 창에 드는 점 수
  baseDays: number;            // 그 앞 비교 창의 점 수
  spark: number[];             // 주 평균, 최근 26주
  sparkRecent: number;         // spark 끝에서 최근 창(4주)
  from: string;
  to: string;
  byGen: GenTrend[];
}

/** 나이대 곡선 다섯 → 추이 하나. 증감은 두 창 모두 검색이 있던 날이 20일 이상인 나이대만 같은 무게로 평균해 센다(자기 최고점 100 인 상대값이라
 *  드문 나이대 하나가 전체를 흔든다). 그런 나이대가 없으면 pct 는 null 이고 그림만 남는다. boardAt 을 주면 오래된 곡선은 증감을 내지 않는다. */
export function combineCurves(curves: GenerationCurve[], boardAt?: string | null): Trend | null {
  const series = curves.filter((c) => Array.isArray(c.points) && c.points.length > 1);
  if (!series.length) return null;
  let start = Infinity, end = -Infinity;
  for (const c of series) for (const [d] of c.points) { const x = toDay(d); if (Number.isNaN(x)) continue; if (x < start) start = x; if (x > end) end = x; }
  if (!Number.isFinite(start) || !Number.isFinite(end)) return null;
  const grids = series.map((c) => ({ c, g: gridOf(c.points, start, end) }));
  const stale = !!boardAt && !Number.isNaN(toDay(boardAt)) && toDay(boardAt) - end > STALE_DAYS;
  const per = grids.map(({ c, g }) => ({ c, g, pct: growthOf(g) }));
  const counted = per.filter((p) => p.pct !== null);
  const use = counted.length ? counted : per;
  const daily = use[0].g.values.map((_, i) => r1(mean(use.map((p) => p.g.values[i]))));
  const pct = counted.length && !stale ? growthOf({ start, end, values: daily }) : null;
  const n = daily.length;
  const byGen = per
    .slice()
    .sort((x, y) => GEN_ORDER.indexOf(x.c.generation) - GEN_ORDER.indexOf(y.c.generation))
    .map((p) => ({ generation: p.c.generation, spark: weekly(p.g.values), peak: p.c.peak_date ?? null, pct: stale ? null : p.pct, counted: p.pct !== null }));
  return {
    pct, counted: counted.length, stale, daily, smooth: movingAverage(daily),
    recentDays: Math.min(WINDOW_DAYS, n), baseDays: Math.max(0, Math.min(WINDOW_DAYS, n - WINDOW_DAYS)),
    spark: weekly(daily), sparkRecent: WINDOW_DAYS / 7, from: dayIso(start), to: dayIso(end), byGen,
  };
}

/* ---- 근거 ---- */

/** 유튜브 주소에서 영상 id — 없으면 null(수집된 영상 근거 다수가 'https://youtube.com/' 처럼 id 없이 온다). */
export function youtubeId(url: string | null | undefined): string | null {
  if (!url) return null;
  const m = url.match(/(?:youtube\.com\/(?:watch\?(?:.*&)?v=|shorts\/|embed\/)|youtu\.be\/)([A-Za-z0-9_-]{11})/);
  return m ? m[1] : null;
}
export const thumbUrl = (id: string) => `https://i.ytimg.com/vi/${id}/mqdefault.jpg`;

const REF_HOST = /(^|\.)(wikipedia\.org|wiktionary\.org|namu\.wiki|knowyourmeme\.com|pixiv\.net|nicovideo\.jp)$/i;
/* 백엔드가 news·web 으로 붙였지만 사람의 글인 곳 — source_domain 값(수집기 코드·한국어 이름)과 주소의 호스트, 둘 다 본다 */
const UGC_NAME = new Set([
  "브런치", "brunch.co.kr", "weverse", "weverse.io", "디시인사이드", "갤러리", "더쿠", "theqoo", "theqoo.net", "인스티즈", "instiz", "instiz.net",
  "에펨코리아", "fmkorea", "루리웹", "ruliweb", "클리앙", "clien", "뽐뿌", "ppomppu", "reddit", "reddit.com", "bsky.app", "bluesky", "lemmy",
  "news.ycombinator.com", "hacker news", "5ch.net", "pantip.com", "dcard.tw", "girlschannel.net", "togetter.com",
  "naver:blog", "naver:cafearticle", "naver:kin", "x.com", "twitter.com", "instagram.com", "threads.net", "facebook.com", "tiktok.com", "youtube:comments",
]);
const UGC_HOST = /(^|\.)(dcinside\.com|theqoo\.net|instiz\.net|fmkorea\.com|ruliweb\.com|clien\.net|ppomppu\.co\.kr|reddit\.com|bsky\.app|ycombinator\.com|5ch\.net|pantip\.com|dcard\.tw|brunch\.co\.kr|weverse\.io|cafe\.naver\.com|kin\.naver\.com|blog\.naver\.com|x\.com|twitter\.com|instagram\.com|threads\.net|facebook\.com|togetter\.com|girlschannel\.net|lemmy\.[a-z]+)$/i;

const hostOf = (url: string) => { try { return new URL(url).hostname.toLowerCase(); } catch { return ""; } };
const hasPath = (url: string) => { try { const u = new URL(url); return u.pathname.length > 1 || u.search.length > 1; } catch { return false; } };
/** 주소 비교용 — 프로토콜·www·m·끝 빗금을 떼고 위키 문서 이름의 공백·밑줄 차이를 없앤다 */
const urlKey = (url: string) => {
  try { const u = new URL(url); return `${u.hostname.replace(/^(www|m)\./, "")}${decodeURIComponent(u.pathname).replace(/[\s_]+/g, "_").replace(/\/$/, "")}${u.search}`.toLowerCase(); } catch { return url; }
};
const titleKey = (t: string) => t.toLowerCase().normalize("NFKC").replace(/[^\p{L}\p{N}]+/gu, "");
/** 수집기가 제목 앞에 되풀이한 출처 이름 */
const LEADING_SOURCE = /^(네이버 뉴스|Naver News|네이버 블로그|위키백과|Wikipedia|Wiktionary|나무위키|Namuwiki)\s*[·:：|-]\s*/i;
const TRAILING_SOURCE = /\s[-–|]\s[^-–|]{2,40}$/;

export type VisibleKind = "wiki" | "news" | "short";
type Ev = { kind: string; source_domain: string; url: string; title?: string | null; observed_at: string };

/** 보여도 되는 근거인가, 그렇다면 어떤 종류로. 커뮤니티·검색 통계·참고 위키가 아닌 웹 문서·첫 화면 주소뿐인 근거는 null. */
export function visibleKind(e: Pick<Ev, "kind" | "source_domain" | "url">): VisibleKind | null {
  if (!hasPath(e.url)) return null;
  if (e.kind === "short") return "short";
  const dom = (e.source_domain ?? "").toLowerCase();
  const host = hostOf(e.url);
  if (UGC_NAME.has(dom) || UGC_HOST.test(host)) return null;
  if (e.kind === "wiki") return "wiki";
  if (e.kind === "web") return REF_HOST.test(dom) || REF_HOST.test(host) ? "wiki" : null;
  if (e.kind === "news") return "news";
  return null;
}

export interface SourceRef { kind: VisibleKind; name: string; title: string; url: string; at: string; license?: string }

const REF_NAME: [RegExp, Record<Locale, string>][] = [
  [/(^|\.)wiktionary\.org$/, { ko: "위키낱말사전", en: "Wiktionary" }],
  [/^ko\.(m\.)?wikipedia\.org$/, { ko: "위키백과", en: "Korean Wikipedia" }],
  [/^en\.(m\.)?wikipedia\.org$/, { ko: "영어 위키백과", en: "Wikipedia" }],
  [/^ja\.(m\.)?wikipedia\.org$/, { ko: "일본어 위키백과", en: "Japanese Wikipedia" }],
  [/^zh\.(m\.)?wikipedia\.org$/, { ko: "중국어 위키백과", en: "Chinese Wikipedia" }],
  [/^th\.(m\.)?wikipedia\.org$/, { ko: "태국어 위키백과", en: "Thai Wikipedia" }],
  [/^id\.(m\.)?wikipedia\.org$/, { ko: "인도네시아어 위키백과", en: "Indonesian Wikipedia" }],
  [/(^|\.)wikipedia\.org$/, { ko: "위키백과", en: "Wikipedia" }],
  [/(^|\.)namu\.wiki$/, { ko: "나무위키", en: "Namuwiki" }],
  [/(^|\.)knowyourmeme\.com$/, { ko: "Know Your Meme", en: "Know Your Meme" }],
  [/(^|\.)pixiv\.net$/, { ko: "pixiv 백과", en: "pixiv Encyclopedia" }],
  [/(^|\.)nicovideo\.jp$/, { ko: "니코니코 대백과", en: "Niconico Pedia" }],
];
const NEWS_NAME: Record<string, Record<Locale, string>> = {
  "n.news.naver.com": { ko: "네이버 뉴스", en: "Naver News" }, "news.naver.com": { ko: "네이버 뉴스", en: "Naver News" },
  "v.daum.net": { ko: "다음 뉴스", en: "Daum News" }, "news.yahoo.co.jp": { ko: "야후! 뉴스", en: "Yahoo! News" },
  "www.youtube.com": { ko: "YouTube", en: "YouTube" }, "youtube.com": { ko: "YouTube", en: "YouTube" }, "youtu.be": { ko: "YouTube", en: "YouTube" },
  "www.tiktok.com": { ko: "TikTok", en: "TikTok" }, "tiktok.com": { ko: "TikTok", en: "TikTok" },
};

const AGGREGATOR = /(^|\.)(news\.google\.com|feedproxy\.google\.com)$/i;
const LICENSE_TAIL = /\s*\((CC BY[^)]*)\)\s*$/i;

/** 출처 이름. 참고 위키는 이름표로, 기사·영상은 주소의 매체(naver:news 로 들어온 기사도 실제 언론사 주소가 있다).
 *  구글 뉴스 RSS 주소는 매체를 알 수 없으니 수집기가 적은 source_domain 을 쓴다. */
export function sourceName(locale: Locale, e: Pick<Ev, "source_domain" | "url">, kind: VisibleKind): string {
  const host = hostOf(e.url);
  const dom = (e.source_domain ?? "").trim();
  if (kind === "wiki") { for (const [re, name] of REF_NAME) if (re.test(host) || re.test(dom)) return name[locale]; }
  if (NEWS_NAME[host]) return NEWS_NAME[host][locale];
  if (/^youtube$/i.test(dom)) return "YouTube";
  if (dom && !/^[a-z]+:/i.test(dom) && !/\.[a-z]{2,}$/i.test(dom)) return dom;   // 수집기가 준 매체 이름('조선일보')
  if (AGGREGATOR.test(host)) return NEWS_NAME[dom]?.[locale] ?? dom.replace(/^(www|m|news|n|mobile)\./, "") ?? host;
  return host.replace(/^(www|m|news|n|mobile)\./, "") || dom;
}

/** 위키 문서 주소의 문서 이름('/wiki/Skibidi_Toilet' → 'Skibidi Toilet') */
const pageName = (url: string) => { try { return decodeURIComponent(new URL(url).pathname.split("/").filter(Boolean).at(-1) ?? "").replace(/_/g, " "); } catch { return ""; } };

/** 화면에 보여도 되는 근거만, 같은 주소·같은 제목은 하나로. 이 말이 제목인 참고 위키 문서 → 다른 참고 문서 → 기사·영상(최근 것부터).
 *  names = [표제어, ...다른 표기]: 이름이 제목에 없는 위키 문서는 그 말이 본문 어딘가에 나올 뿐일 수 있어 뒤로 둔다 — 빼지는 않는다. */
export function visibleEvidence<T extends Ev>(evs: T[] | null | undefined, locale: Locale, names: string[] = []): SourceRef[] {
  const keys = names.map(titleKey).filter((k) => k.length > 0);
  const seenUrl = new Set<string>();
  const seenTitle = new Set<string>();
  const rows: { ref: SourceRef; rank: number }[] = [];
  const ordered = (evs ?? []).slice().sort((a, b) => Number(b.kind === "wiki") - Number(a.kind === "wiki") || (b.observed_at ?? "").localeCompare(a.observed_at ?? ""));
  for (const e of ordered) {
    const kind = visibleKind(e);
    if (!kind) continue;
    const name = sourceName(locale, e, kind);
    let title = (e.title ?? "").trim().replace(LEADING_SOURCE, "");
    const lic = LICENSE_TAIL.exec(title);
    if (lic) title = title.slice(0, lic.index);
    // 제목 끝의 ' - v.daum.net', ' - 조선비즈 - Chosunbiz' 처럼 출처를 되풀이한 꼬리만 뗀다(출처 이름·수집기 코드·주소와 겹칠 때)
    const tailKeys = [name, e.source_domain ?? "", hostOf(e.url).replace(/^(www|m|news|n|mobile)\./, "")].map(titleKey).filter((k) => k.length >= 3);
    for (let i = 0; i < 2; i++) {
      const tail = TRAILING_SOURCE.exec(title);
      if (!tail) break;
      const tk = titleKey(tail[0]);
      if (tk.length >= 3 && tailKeys.some((k) => k.includes(tk) || tk.includes(k.slice(0, 5)))) title = title.slice(0, tail.index);
      else break;
    }
    title = title.trim() || name;
    const uk = urlKey(e.url);
    const tk = `${kind}:${titleKey(title)}`;
    if (seenUrl.has(uk) || (tk.length > 8 && seenTitle.has(tk))) continue;
    seenUrl.add(uk);
    seenTitle.add(tk);
    const page = titleKey(pageName(e.url));
    const named = kind === "wiki" && keys.some((k) => titleKey(title).includes(k) || (page.length > 0 && page.includes(k)));
    rows.push({ rank: named ? 0 : kind === "wiki" ? 1 : 2, ref: { kind, name, title, url: e.url, at: e.observed_at, license: lic?.[1] } });
  }
  return rows.sort((a, b) => a.rank - b.rank || b.ref.at.localeCompare(a.ref.at)).map((r) => r.ref);
}

/* ---- 쓸 때 조심 ---- */

export interface RiskNote { text: string; quote?: string }   // quote 는 사전 뜻풀이의 주의점(한국어) — 인용 부호로 보인다

const RISK_TEXT: Record<Locale, Record<string, string>> = {
  ko: {
    sensitive: "민감한 맥락에서 쓰인 글이 {n}건 있어요.",
    negative: "쓰인 글의 {n}%가 부정적이었어요.",
    dict: "사전 뜻풀이에 적힌 주의점:",
    thin: "그 뜻으로 쓰인 글이 {n}건뿐이라 아직 판단하지 않았어요.",
    none: "그 뜻으로 쓰인 글을 아직 찾지 못해 판단하지 않았어요.",
    clean: "살펴본 글 {n}건에서 민감한 맥락을 찾지 못했어요.",
    stale: "뉴스에 오른 뒤 언급이 줄고 있어 식상해 보일 수 있어요.",
  },
  en: {
    sensitive: "{n} uses appeared in sensitive contexts.",
    negative: "{n}% of the uses we read were negative.",
    dict: "The dictionary entry itself notes a caution:",
    thin: "Only {n} uses carry this meaning, so it is not judged yet.",
    none: "No use with this meaning has been found yet, so it is not judged.",
    clean: "No sensitive context in the {n} uses we read.",
    stale: "Mentions fell after news coverage, so it may look stale.",
  },
};

/** 백엔드 규칙이 남긴 사유를 쉬운 말로. 커뮤니티 글의 예문·사이트 이름은 떼고, 사전 뜻풀이의 주의점은 사전의 글이므로 그대로 인용한다. */
export function riskNotes(reasons: string[] | null | undefined, locale: Locale): RiskNote[] {
  const T = RISK_TEXT[locale];
  const fill = (t: string, n: string) => t.replace("{n}", n);
  const out: RiskNote[] = [];
  const push = (n: RiskNote) => { if (!out.some((o) => o.text === n.text && o.quote === n.quote)) out.push(n); };
  for (const raw of reasons ?? []) {
    const r = raw.trim();
    if (!r || /^[“"]/.test(r)) continue;
    let m = /^위험 유형이 붙은 근거 (\d+)건/.exec(r);
    if (m) { push({ text: fill(T.sensitive, m[1]) }); continue; }
    m = /^부정적으로 쓰인 근거가 (\d+)%/.exec(r);
    if (m) { push({ text: fill(T.negative, m[1]) }); continue; }
    m = /^사전 뜻풀이에 적힌 주의점:\s*[“"](.+?)[”"]/.exec(r);
    if (m) { push({ text: T.dict, quote: m[1] }); continue; }
    m = /^그 뜻으로 쓰인 근거가 (\d+)건뿐/.exec(r);
    if (m) { push({ text: m[1] === "0" ? T.none : fill(T.thin, m[1]) }); continue; }
    m = /^분류된 근거 (\d+)건에 위험 신호가 없다/.exec(r);
    if (m) { push({ text: fill(T.clean, m[1]) }); continue; }
    if (/뉴스에 오른 뒤 언급이 줄고/.test(r)) { push({ text: T.stale }); continue; }
    // 모르는 문장: 인용이나 사이트 이름이 들어 있으면 내지 않는다(누구의 글인지 알 수 없다). 한국어 화면에서만 원문으로.
    if (locale === "ko" && !/[“”"「」]/.test(r) && !/\([\w.-]+\.[a-z]{2,}\)/i.test(r) && r.length < 120) push({ text: r });
  }
  return out.slice(0, 3);
}

export const fmtDay = (iso: string | null | undefined) => (iso ? iso.slice(0, 10).replace(/-/g, ".") : "");
export const fmtMonth = (iso: string | null | undefined) => (iso ? iso.slice(0, 7).replace("-", ".") : "");
export const fmtShort = (iso: string | null | undefined) => (iso ? iso.slice(5, 10).replace("-", ".") : "");

/** 최근 며칠 안에 사전에 새로 오른 표제어 id — 목록의 '새로 올라옴' 표시 */
export function newlyVerified(items: Pick<UpdateItem, "kind" | "term_id" | "at">[], days = 7, ref = Date.now()): Set<string> {
  const from = ref - days * 86_400_000;
  const s = new Set<string>();
  for (const i of items) if (i.kind === "verified" && i.term_id && Date.parse(i.at) >= from) s.add(i.term_id);
  return s;
}

/** 표제어 이름의 '보이는 길이' — 한글·한자·가나는 1, 라틴 소문자 0.56 … 타일·머리 글자 크기를 정한다 */
export function visualLength(text: string): number {
  let n = 0;
  for (const ch of text) {
    if (/[ᄀ-ᇿ぀-ヿ㐀-鿿가-힯＀-￯]/.test(ch)) n += 1;
    else if (/[฀-๿]/.test(ch)) n += 0.62;
    else if (/\s/.test(ch)) n += 0.3;
    else if (/[A-Z]/.test(ch)) n += 0.68;
    else n += 0.56;
  }
  return n;
}
/** 글자 크기 단계: xl(짧은 낱말) → s(긴 이름) */
export const fitClass = (name: string) => { const n = visualLength(name); return n <= 5 ? "fit-xl" : n <= 9 ? "fit-l" : n <= 14 ? "fit-m" : "fit-s"; };

/* ---- 화면 행 모델: 대시보드 카드 + 추이. 클라이언트로 내려가므로 필요한 것만. ---- */
export interface Row {
  id: string;
  name: string;
  lang: string;
  category: string;
  gloss: string;
  glossLang?: string;            // 영어 화면에 번역이 없어 한국어 뜻이 나갈 때 "ko"
  stage: string;                 // Lifecycle
  diffusion: string | null;
  risk: "none" | "caution" | "avoid" | null;
  riskNotes: RiskNote[];
  regions: string[];
  lastUsed: string | null;       // 고른 지역에서 마지막으로 쓰인 때(없으면 마지막 확인)
  pct: number | null;
  spark: number[] | null;        // pct 를 셀 수 있을 때만 — 셀 수 없는 밈은 선도 그리지 않는다
  sparkRecent: number;
  byGen: GenTrend[] | null;
  from: string | null;
  to: string | null;
  stale: boolean;
  sources: SourceRef[];
  thumb: string | null;          // 유튜브 썸네일 — 영상 근거에 id 가 있을 때만
  video: string | null;
  isNew: boolean;
  list: KeywordList;
}

export function toRow(card: KeywordCard, trend: Trend | null, newIds: Set<string>, locale: Locale, list: KeywordList): Row {
  const sources = visibleEvidence(card.evidences, locale, [card.canonical]);
  const short = sources.find((e) => e.kind === "short" && youtubeId(e.url));
  const vid = short ? youtubeId(short.url) : null;
  const gloss = (locale === "en" ? card.gloss_en : card.gloss_ko) || card.gloss_ko || card.gloss_en || "";
  const countable = !!trend && trend.pct !== null;
  return {
    id: card.term_id,
    name: card.canonical,
    lang: card.lang,
    category: card.category,
    gloss,
    glossLang: locale === "en" && !card.gloss_en && card.gloss_ko ? "ko" : undefined,
    stage: card.lifecycle ?? "unknown",
    diffusion: card.diffusion ?? null,
    risk: card.risk_level ?? null,
    riskNotes: riskNotes(card.risk_reasons, locale),
    regions: card.regions ?? [],
    lastUsed: card.last_used ?? card.last_seen ?? null,
    pct: trend?.pct ?? null,
    spark: countable ? trend!.spark : null,
    sparkRecent: trend?.sparkRecent ?? 4,
    byGen: trend?.byGen ?? null,
    from: trend?.from ?? null,
    to: trend?.to ?? null,
    stale: trend?.stale ?? false,
    sources: sources.slice(0, 4),
    thumb: vid ? thumbUrl(vid) : null,
    video: short?.url ?? null,
    isNew: newIds.has(card.term_id),
    list,
  };
}

/** 이번 주 주목 셋: 쓰이는·식는 목록을 통틀어 검색 관심이 가장 많이 늘어난 순(식는 목록의 급등도 오른다 — 타일이 단계를 말한다).
 *  늘어난 밈이 셋 미만이면 쓰이는 목록 앞에서 채우되 늘었다고 말하지 않는다. */
export function pickSpotlight(rising: Row[], fading: Row[], n = 3): { rows: Row[]; byGrowth: boolean } {
  const pool = [...rising, ...fading].filter((r) => r.risk !== "avoid");
  const grown = pool.filter((r) => r.pct !== null && r.pct > 0).sort((a, b) => b.pct! - a.pct!).slice(0, n);
  const fill = rising.filter((r) => r.risk !== "avoid" && !grown.includes(r)).slice(0, n - grown.length);
  return { rows: [...grown, ...fill], byGrowth: grown.length > 0 };
}

/** 검색어로 행 거르기 — 이름·뜻 안에 그대로 들어 있는 것만(느슨한 매칭은 판정이 아니므로 하지 않는다) */
export function filterRows(rows: Row[], q: string): Row[] {
  const needle = q.trim().toLowerCase();
  if (!needle) return rows;
  return rows.filter((r) => r.name.toLowerCase().includes(needle) || r.gloss.toLowerCase().includes(needle));
}
