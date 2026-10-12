/* 시안 F(에디토리얼) 규칙 — 판(edition) 주소, 호(issue) 이름, 꼭지 나누기, 표지 고르기, 네이버 검색 추세, 보이는 출처, 조심 이유 문장,
   지난 호 이후 달라진 것의 판 걸러내기. 판정은 여기(데이터 규칙)가 하고 화면은 그리기만 한다. 공용 파일은 읽기만 한다. */
import type { UpdateRow } from "@/lib/data";
import type { LabLocale as Locale } from "@/lib/i18n";
import { riskOf } from "@/lib/keyword";
import { regionLabel, sourceName, termLangLabel } from "@/lib/labels";
import { scriptLang } from "@/lib/lang";
import { TARGET_REGIONS } from "@/lib/reader";
import { cleanSource } from "@/lib/sources";
import type { GenerationCurve } from "@/lib/trends/types";
import type { Evidence, KeywordBoard, KeywordCard, Lifecycle } from "@/lib/types";
import { fe } from "./copy";

export const BASE = "/lab/f-editorial";
/** 판 — 목표 지역 열 곳, 세계판, 전체판 */
export const EDITIONS = [...TARGET_REGIONS, "GLOBAL", "ALL"];

type SP = Record<string, string | string[] | undefined>;
const one = (v: string | string[] | undefined) => ([v].flat()[0] ?? "").trim();

export function parseEdition(sp: SP): string {
  const e = one(sp.edition).toUpperCase();
  return EDITIONS.includes(e) ? e : "KR";
}
export function parsePage(sp: SP): number {
  const n = Number.parseInt(one(sp.page), 10);
  return Number.isFinite(n) && n > 1 && n < 100 ? n : 1;
}
export const parseQuery = (sp: SP) => one(sp.q).slice(0, 80);

/** 대시보드에 물을 지역 — 전체판은 빈 목록(목표 지역 전부) */
export const editionRegions = (edition: string) => (edition === "ALL" ? [] : [edition]);
/** 판이 다루는 지역 집합 — 카드·검색 급증의 지역과 맞춰 볼 때 */
export const editionScope = (edition: string) => new Set(edition === "ALL" ? TARGET_REGIONS : [edition]);
/** 추천 흐름으로 가는 주소 — 전체판은 목표 지역 전부, 세계판은 지역을 정하지 않는다 */
export function recommendHref(edition: string): string {
  const regions = edition === "ALL" ? TARGET_REGIONS : edition === "GLOBAL" ? [] : [edition];
  return regions.length ? `/recommend?regions=${encodeURIComponent(regions.join(","))}` : "/recommend";
}

export function editionName(locale: Locale, edition: string): string {
  if (edition === "ALL") return fe(locale, "edition_all");
  if (edition === "GLOBAL") return fe(locale, "edition_global");
  return `${regionLabel(locale, edition)}${fe(locale, "edition_suffix")}`;
}

export const issueHref = (edition: string, extra?: Record<string, string>) => {
  const q = new URLSearchParams({ edition, ...extra });
  return `${BASE}?${q}`;
};
export const entryHref = (termId: string, edition: string) => `${BASE}/m/${encodeURIComponent(termId)}?edition=${encodeURIComponent(edition)}`;

/** 호 이름 — 보드가 만들어진 주(월요일–일요일, 서울 기준). 호 번호는 지어내지 않는다. */
export function issueRange(iso: string | null | undefined, locale: Locale): string | null {
  if (!iso) return null;
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return null;
  const local = new Date(t + 9 * 3600_000);
  const dow = (local.getUTCDay() + 6) % 7;
  const mon = new Date(Date.UTC(local.getUTCFullYear(), local.getUTCMonth(), local.getUTCDate() - dow));
  const sun = new Date(mon.getTime() + 6 * 86_400_000);
  if (locale === "ko") {
    const sameMonth = sun.getUTCMonth() === mon.getUTCMonth();
    return `${mon.getUTCFullYear()}년 ${mon.getUTCMonth() + 1}월 ${mon.getUTCDate()}일 – ${sameMonth ? "" : `${sun.getUTCMonth() + 1}월 `}${sun.getUTCDate()}일`;
  }
  const M = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return `${mon.getUTCDate()} ${M[mon.getUTCMonth()]} – ${sun.getUTCDate()} ${M[sun.getUTCMonth()]} ${sun.getUTCFullYear()}`;
}

/* ── 꼭지(rubric) ────────────────────────────────────────────────────────────
   생애주기·목록 규칙으로만 나눈다. 뜨는 중·절정은 비어도 그렇다고 말한다(마케터에게는 '없음' 도 정보다).
   앞 꼭지에 실린 밈은 다음 꼭지에 다시 싣지 않는다 — 조심 목록만 예외다: '무엇을 피할까' 의 점검표라 앞에 실린 밈도 다시 적는다. */
export type RubricKey = "hot" | "peak" | "steady" | "unknown" | "fading" | "caution";
/** total 은 목록 전체 건수(쪽 밖 포함) — 백엔드가 세는 식는 중·조심만 알 수 있다. 나머지는 이 쪽에 실린 수. */
export interface Rubric { key: RubricKey; cards: KeywordCard[]; total: number; alwaysShow: boolean }

export function rubrics(board: KeywordBoard, shown: Set<string>): Rubric[] {
  const seen = new Set(shown);
  const take = (list: KeywordCard[], pred: (c: KeywordCard) => boolean) => {
    const out: KeywordCard[] = [];
    for (const c of list) if (!seen.has(c.term_id) && pred(c)) { seen.add(c.term_id); out.push(c); }
    return out;
  };
  const hot = take(board.rising, (c) => c.lifecycle === "emerging" || c.lifecycle === "rising");
  const peak = take(board.rising, (c) => c.lifecycle === "peak");
  const unknown = take(board.rising, (c) => c.lifecycle === "unknown");
  const steady = take(board.rising, () => true);
  const fading = take(board.fading, () => true);
  return [
    { key: "hot", cards: hot, total: hot.length, alwaysShow: true },
    { key: "peak", cards: peak, total: peak.length, alwaysShow: true },
    { key: "steady", cards: steady, total: steady.length, alwaysShow: false },
    { key: "unknown", cards: unknown, total: unknown.length, alwaysShow: false },
    { key: "fading", cards: fading, total: board.totals.fading, alwaysShow: false },
    { key: "caution", cards: board.caution, total: board.totals.caution, alwaysShow: false },
  ];
}

/** 보드의 카드 전부, 같은 밈은 한 번만(주의 밈은 두 목록에 있다) */
export function uniqueCards(board: KeywordBoard): KeywordCard[] {
  const seen = new Map<string, KeywordCard>();
  for (const c of [...board.rising, ...board.fading, ...board.caution]) if (!seen.has(c.term_id)) seen.set(c.term_id, c);
  return [...seen.values()];
}

export function glossOf(card: Pick<KeywordCard, "gloss_ko" | "gloss_en">, locale: Locale): { text: string; lang?: string } {
  if (locale === "en") return card.gloss_en ? { text: card.gloss_en } : { text: card.gloss_ko, lang: "ko" };
  return card.gloss_ko ? { text: card.gloss_ko } : { text: card.gloss_en, lang: "en" };
}

/** 이름·뜻으로 찾기 — 느슨하게(대소문자·공백 무시) */
export function matchCard(card: KeywordCard, q: string): boolean {
  const k = q.toLowerCase().replace(/\s+/g, "");
  if (!k) return false;
  return [card.canonical, card.gloss_ko, card.gloss_en].some((s) => (s ?? "").toLowerCase().replace(/\s+/g, "").includes(k));
}

/* ── 네이버 검색 추세 ─────────────────────────────────────────────────────────
   나이대마다 곡선의 마지막 날을 기준으로 달력 28일 창 둘(최근 4주·이전 4주)을 견준다. 창마다 자료가 20일 이상 있어야 하고,
   없는 날은 0 으로 보아 같은 28일로 나눈다. 밈 하나의 값은 나이대별 변화의 가운데 값이며, 자료가 있는 나이대가 셋 미만이면 %를 내지 않는다.
   곡선의 끝이 보드 시각보다 14일 넘게 오래됐으면(수집이 멈춘 말) 추세를 내지 않는다. */
const DAY = 86_400_000;
const WINDOW = 28;
const MIN_DAYS = 20;
const STALE_DAYS = 14;
export const GROWTH_MIN = 15;   // 이만큼(%) 이상 늘어야 '늘어난 밈'
const dayMs = (d: string) => Date.parse(`${d.slice(0, 10)}T00:00:00Z`);
const avg = (xs: number[]) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0);

export interface AgeChange {
  generation: string;
  latest: number;             // 최근 4주 하루 평균(없는 날 0)
  previous: number;           // 이전 4주 하루 평균
  change: number | null;      // % — 창 하나라도 20일 미만이거나 이전이 0 이면 null
  end: string | null;
  peak: string | null;
  points: [string, number][]; // 날짜순
}

export function ageChange(c: GenerationCurve): AgeChange {
  const points = [...c.points].filter((p) => Array.isArray(p) && typeof p[1] === "number").sort((a, b) => a[0].localeCompare(b[0]));
  const end = points.at(-1)?.[0] ?? null;
  let a = 0, na = 0, b = 0, nb = 0;
  if (end) {
    const e = dayMs(end);
    for (const [d, v] of points) {
      const age = (e - dayMs(d)) / DAY;
      if (age < WINDOW) { a += v; na++; } else if (age < WINDOW * 2) { b += v; nb++; }
    }
  }
  const change = na >= MIN_DAYS && nb >= MIN_DAYS && b > 0 ? Math.round((a / b - 1) * 100) : null;
  return { generation: c.generation, latest: a / WINDOW, previous: b / WINDOW, change, end, peak: c.peak_date ?? null, points };
}

export interface SearchTrend {
  pct: number | null;   // 나이대별 변화의 가운데 값. 자료가 모자라거나 오래됐으면 null
  weekly: number[];     // 전 나이대 평균의 주 평균, 오래된 것부터(최대 26주, 0–100)
  valid: number;        // 변화를 잴 수 있었던 나이대 수
  up: number;           // 그 가운데 15% 이상 늘어난 나이대 수
  end: string | null;
  stale: boolean;
  ages: AgeChange[];
}

export function searchTrend(curves: GenerationCurve[], boardAt?: string | null): SearchTrend | null {
  const ages = curves.filter((c) => c.points.length > 1).map(ageChange);
  if (!ages.length) return null;
  const end = ages.map((x) => x.end).filter((d): d is string => !!d).sort().at(-1) ?? null;
  const at = boardAt ? Date.parse(boardAt) : NaN;
  const stale = !!end && !Number.isNaN(at) && at - dayMs(end) > STALE_DAYS * DAY;
  const vals = ages.map((x) => x.change).filter((v): v is number => v !== null).sort((x, y) => x - y);
  const median = vals.length ? (vals.length % 2 ? vals[(vals.length - 1) / 2] : Math.round((vals[vals.length / 2 - 1] + vals[vals.length / 2]) / 2)) : null;
  const pct = !stale && vals.length >= 3 ? median : null;
  const byDay = new Map<string, number[]>();
  for (const x of ages) for (const [d, v] of x.points) byDay.set(d, [...(byDay.get(d) ?? []), v]);
  const weekly: number[] = [];
  if (end) {
    const e = dayMs(end);
    const buckets: number[][] = [];
    for (const [d, vs] of byDay) {
      const w = Math.floor((e - dayMs(d)) / DAY / 7);
      if (w >= 0 && w < 26) (buckets[w] ??= []).push(avg(vs));
    }
    for (let w = 25; w >= 0; w--) if (buckets[w]?.length) weekly.push(avg(buckets[w]));
  }
  return { pct, weekly, valid: vals.length, up: vals.filter((v) => v >= GROWTH_MIN).length, end, stale, ages };
}

/** '검색이 늘어난 밈' 에 싣는 기준 — 셋 이상 나이대에 자료가 있고, 절반 넘는 나이대에서 15% 이상 늘고, 가운데 값도 15% 이상 */
export const searchedMore = (t: SearchTrend | null | undefined): t is SearchTrend => !!t && t.pct !== null && t.pct >= GROWTH_MIN && t.up > t.valid / 2;

/** "+46%" / "−9%" — 기호는 글자로, 색으로 방향을 말하지 않는다 */
export const fmtPct = (pct: number) => (pct > 0 ? `+${pct}%` : pct < 0 ? `−${Math.abs(pct)}%` : "0%");

/* ── 표지 고르기 ─────────────────────────────────────────────────────────────
   늘어나는 중(emerging·rising)이고 조심할 점이 없는 밈 → 검색이 가장 많이 늘어난 밈 → 지금 쓰이는 밈 가운데 조심할 점이 없는 첫 밈 →
   그것도 없으면 첫 밈을 조심할 점과 함께. 어느 규칙으로 골랐는지 화면에 적는다. */
export type CoverRule = "rising" | "growth" | "first" | "caution";
export function pickCover(board: KeywordBoard, trends: Map<string, SearchTrend | null>): { card: KeywordCard; rule: CoverRule } | null {
  const ok = (c: KeywordCard) => { const r = riskOf(c); return r !== "caution" && r !== "avoid"; };
  const rising = board.rising;
  const a = rising.find((c) => (c.lifecycle === "emerging" || c.lifecycle === "rising") && ok(c));
  if (a) return { card: a, rule: "rising" };
  const g = rising.filter((c) => ok(c) && searchedMore(trends.get(c.term_id))).sort((x, y) => trends.get(y.term_id)!.pct! - trends.get(x.term_id)!.pct!)[0];
  if (g) return { card: g, rule: "growth" };
  const f = rising.find(ok);
  if (f) return { card: f, rule: "first" };
  const any = rising[0] ?? board.fading[0];
  return any ? { card: any, rule: "caution" } : null;
}

/* ── 보이는 출처 (자료 정책 09-29) ──────────────────────────────────────────
   위키·기사·영상만. 커뮤니티·SNS·블로그 글은 제목·인용·사이트 이름을 내지 않는다 — 수집기가 news/web 으로 넣은 것도 이름으로 거른다.
   첫 화면 주소뿐인 근거(https://youtube.com/)는 눌러도 그 글로 가지 않으므로 내지 않는다. */
const REFERENCE = /(^|\.)((\w+\.)?wikipedia\.org|(\w+\.)?wiktionary\.org|namu\.wiki|knowyourmeme\.com|pixiv\.net|nicovideo\.jp|wikiwiki\.jp)$/i;
const UGC_NAME = new Set([
  "naver:blog", "naverblog", "naver:cafearticle", "naver:kin", "브런치", "brunch.co.kr", "weverse", "디시인사이드", "갤러리", "더쿠", "theqoo",
  "theqoo.net", "인스티즈", "instiz", "instiz.net", "에펨코리아", "fmkorea", "루리웹", "ruliweb", "클리앙", "clien", "뽐뿌", "ppomppu", "reddit",
  "reddit.com", "bsky.app", "bluesky", "news.ycombinator.com", "hacker news", "5ch.net", "pantip.com", "dcard.tw", "girlschannel.net",
  "togetter.com", "lemmy", "x.com", "twitter.com", "instagram.com", "threads.net", "facebook.com", "tiktok.com", "tistory",
]);
const UGC_HOST = /(^|\.)(dcinside\.com|theqoo\.net|instiz\.net|fmkorea\.com|ruliweb\.com|clien\.net|ppomppu\.co\.kr|reddit\.com|bsky\.app|ycombinator\.com|5ch\.net|pantip\.com|dcard\.tw|brunch\.co\.kr|weverse\.io|cafe\.naver\.com|kin\.naver\.com|blog\.naver\.com|tistory\.com|x\.com|twitter\.com|threads\.net|facebook\.com)$/i;
const VIDEO_HOST = /(^|\.)(youtube\.com|youtu\.be|tiktok\.com|instagram\.com)$/i;
const hostOf = (url: string) => { try { return new URL(url).hostname.toLowerCase(); } catch { return ""; } };
const hasPath = (url: string) => { try { return !["", "/"].includes(new URL(url).pathname); } catch { return false; } };

function isUgc(e: Pick<Evidence, "kind" | "source_domain" | "url">): boolean {
  if (e.kind === "community") return true;
  const dom = (e.source_domain ?? "").toLowerCase();
  const host = hostOf(e.url);
  return UGC_NAME.has(dom) || UGC_HOST.test(host) || /blog|브런치|brunch|weverse|cafe|tistory/.test(dom) || /^blog\./.test(host);
}

export type SourceKind = "wiki" | "news" | "video";
export function visibleKind(e: Pick<Evidence, "kind" | "source_domain" | "url">): SourceKind | null {
  if (!e.url || !hasPath(e.url)) return null;
  if (e.kind === "short") return "video";   // 쇼츠 영상은 보인다(영상 댓글·글은 community 종류로 따로 온다)
  if (isUgc(e)) return null;
  const host = hostOf(e.url);
  const dom = (e.source_domain ?? "").toLowerCase();
  if (e.kind === "wiki") return "wiki";
  if (e.kind === "web") return REFERENCE.test(host) || REFERENCE.test(dom) ? "wiki" : null;
  if (e.kind === "news") return VIDEO_HOST.test(host) || dom === "youtube" || dom === "youtu.be" ? "video" : "news";
  return null;
}

export interface SourceItem {
  id: string;
  kind: SourceKind;
  named: boolean;      // 참고 문서의 제목(또는 문서 주소)이 이 밈의 이름이다
  source: string;      // "위키백과", "조선일보", "YouTube"
  title: string;
  titleLang?: string;
  url: string;
  date: string;
}

const NEWS_NAME: Record<string, Record<Locale, string>> = {
  "v.daum.net": { ko: "다음 뉴스", en: "Daum News" },
  "n.news.naver.com": { ko: "네이버 뉴스", en: "Naver News" },
  "news.naver.com": { ko: "네이버 뉴스", en: "Naver News" },
  "youtube": { ko: "YouTube", en: "YouTube" },
  "youtu.be": { ko: "YouTube", en: "YouTube" },
  "youtube.com": { ko: "YouTube", en: "YouTube" },
  "tiktok.com": { ko: "TikTok", en: "TikTok" },
  "instagram.com": { ko: "Instagram", en: "Instagram" },
  "knowyourmeme": { ko: "Know Your Meme", en: "Know Your Meme" },
  "knowyourmeme.com": { ko: "Know Your Meme", en: "Know Your Meme" },
};

/** 참고 문서의 이름 — 언어판 위키백과·위키낱말사전은 '일본어 위키백과' 처럼 짓는다 */
function referenceName(host: string, locale: Locale): string {
  const known = sourceName(locale, host);
  if (known !== host) return known;
  const m = /^([a-z]{2,3})\.(?:m\.)?(wikipedia|wiktionary)\.org$/.exec(host);
  if (m) {
    const lang = termLangLabel(locale, m[1]);
    const base = m[2] === "wikipedia" ? (locale === "ko" ? "위키백과" : "Wikipedia") : (locale === "ko" ? "위키낱말사전" : "Wiktionary");
    return lang !== m[1] ? `${lang} ${base}` : base;
  }
  if (/namu\.wiki$/.test(host)) return locale === "ko" ? "나무위키" : "Namuwiki";
  if (/knowyourmeme\.com$/.test(host)) return "Know Your Meme";
  if (/pixiv\.net$/.test(host)) return locale === "ko" ? "pixiv 백과사전" : "pixiv Encyclopedia";
  if (/nicovideo\.jp$/.test(host)) return locale === "ko" ? "니코니코 대백과" : "Niconico Pedia";
  return host.replace(/^www\./, "");
}

/** 기사·영상의 출처 이름 — 네이버 뉴스 검색으로 들어온 기사는 주소의 언론사 도메인이 출처다 */
function reportName(e: Evidence, kind: SourceKind, locale: Locale): string {
  const host = hostOf(e.url);
  const dom = (e.source_domain ?? "").toLowerCase();
  if (kind === "video") return NEWS_NAME[host.replace(/^(www|m)\./, "")]?.[locale] ?? NEWS_NAME[dom]?.[locale] ?? host.replace(/^www\./, "");
  if (dom === "naver:news") return host.replace(/^(www|m|news|n|mobile)\./, "") || sourceName(locale, e.source_domain);
  return NEWS_NAME[dom]?.[locale] ?? sourceName(locale, e.source_domain);
}

/** 주소 비교용 — 프로토콜·www·m·끝 빗금을 떼고, 위키 문서 이름의 공백·밑줄 차이를 없앤다 */
const urlKey = (url: string) => {
  try {
    const u = new URL(url);
    return `${u.hostname.replace(/^(www|m)\./, "")}${decodeURIComponent(u.pathname).replace(/[\s_]+/g, "_").replace(/\/$/, "")}${u.search}`.toLowerCase();
  } catch { return url; }
};
const titleKey = (t: string) => t.toLowerCase().normalize("NFKC").replace(/[^\p{L}\p{N}]+/gu, "");
const pageName = (url: string) => { try { return decodeURIComponent(new URL(url).pathname.split("/").filter(Boolean).at(-1) ?? ""); } catch { return ""; } };
const LEADING_SOURCE = /^(네이버 뉴스|Naver News|위키백과|Wikipedia|Wiktionary|나무위키)\s*[·:：|-]\s*/i;
/** 제목 끝에 되풀이된 출처 이름(" - Chronicle-Tribune")을 뗀다 — 출처 이름에 붙임표가 있어 공용 cleanSource 가 놓치는 꼴. 같은 기사가 여러 포털에 실린 것을 한 번만 세려면 필요하다. */
function stripTail(title: string, e: Evidence): string {
  const at = Math.max(title.lastIndexOf(" - "), title.lastIndexOf(" – "), title.lastIndexOf(" | "));
  if (at < 0) return title;
  const tail = titleKey(title.slice(at + 3));
  const host = hostOf(e.url).replace(/^(www|m)\./, "");
  const candidates = [e.source_domain ?? "", host, host.split(".")[0]].map(titleKey).filter((k) => k.length > 2);
  return tail && candidates.includes(tail) ? title.slice(0, at).trim() : title;
}

/** 출처 목록. names = [표제어, ...다른 표기]. 같은 주소·같은 제목(여러 포털에 실린 기사)은 한 번만.
 *  순서: 이 밈이 제목인 참고 문서 → 다른 참고 문서 → 기사·영상(최근 먼저). */
export function sourceItems(evidences: Evidence[], names: string[], locale: Locale): SourceItem[] {
  const keys = names.map(titleKey).filter((k) => k.length > 0);
  const rows: { item: SourceItem; rank: number }[] = [];
  const seenUrl = new Set<string>();
  const seenTitle = new Set<string>();
  const ordered = [...evidences].sort((a, b) => Number(b.kind === "wiki") - Number(a.kind === "wiki") || b.observed_at.localeCompare(a.observed_at));
  for (const e of ordered) {
    const kind = visibleKind(e);
    if (!kind) continue;
    const clean = cleanSource(e, names[0] ?? "", locale);
    const title = stripTail(clean.title.replace(LEADING_SOURCE, "").trim(), e) || clean.title;
    const uk = urlKey(e.url);
    const tk = `${kind}:${titleKey(title)}`;
    if (seenUrl.has(uk) || (titleKey(title).length > 4 && seenTitle.has(tk))) continue;
    seenUrl.add(uk);
    seenTitle.add(tk);
    const page = titleKey(pageName(e.url));
    const named = kind === "wiki" && keys.some((k) => titleKey(title).includes(k) || (page.length > 0 && page.includes(k)));
    rows.push({
      rank: named ? 0 : kind === "wiki" ? 1 : 2,
      item: { id: e.evidence_id, kind, named, source: kind === "wiki" ? referenceName(hostOf(e.url), locale) : reportName(e, kind, locale), title, titleLang: scriptLang(title), url: e.url, date: e.observed_at },
    });
  }
  return rows.sort((a, b) => a.rank - b.rank || b.item.date.localeCompare(a.item.date)).map((r) => r.item);
}

/** 유래 밑에 붙이는 근거 둘 — 이 밈의 참고 문서, 없으면 다른 참고 문서, 그것도 없으면 가장 먼저 나온 기사·영상 */
export function originRefs(list: SourceItem[]): SourceItem[] {
  const named = list.filter((s) => s.named);
  if (named.length) return named.slice(0, 2);
  const refs = list.filter((s) => s.kind === "wiki");
  if (refs.length) return refs.slice(0, 2);
  return [...list].sort((a, b) => a.date.localeCompare(b.date)).slice(0, 2);
}

/* ── 조심 이유 ───────────────────────────────────────────────────────────────
   규칙이 남긴 이유는 한국어 기계 문장이고 커뮤니티 글 인용과 사이트 이름이 붙어 있다. 아는 꼴은 쉬운 문장(두 언어)으로 옮기고,
   사전 뜻풀이의 주의점은 그 글을 그대로 살린다. 백분율은 표본이 작을 수 있어 '전부·절반 넘게·일부' 로만 말한다. 모르는 꼴은 내지 않는다. */
export interface Reason { text: string; lang?: string }

export function plainReason(reasons: string[] | null | undefined, locale: Locale): Reason | null {
  for (const raw of reasons ?? []) {
    const r = raw.trim();
    if (r === "검수자가 정한 수준") return { text: fe(locale, "risk_by_reviewer") };
    let m = /^사전 뜻풀이에 적힌 주의점:\s*[“"]?([\s\S]*?)[”"]?\s*$/u.exec(r);
    if (m && m[1].trim()) return { text: fe(locale, "reason_note", { text: m[1].trim() }), lang: locale === "en" ? "ko" : undefined };
    m = /^부정적으로 쓰인 근거가 (\d+)%/u.exec(r);
    if (m) { const n = Number(m[1]); return { text: fe(locale, n >= 100 ? "reason_neg_all" : n >= 50 ? "reason_neg_half" : "reason_neg_some") }; }
    // 영어는 하나일 때 다른 문장(_1). 한국어 문구에는 _1 키가 없어 같은 문장으로 돌아간다
    const one = (key: string, n: number) => fe(locale, n === 1 && locale === "en" ? `${key}_1` : key, { n });
    m = /^위험 유형이 붙은 근거 (\d+)건/u.exec(r);
    if (m) return { text: one("reason_flag", Number(m[1])) };
    m = /^그 뜻으로 쓰인 근거가 (\d+)건뿐/u.exec(r);
    if (m) return { text: one("reason_few", Number(m[1])) };
    m = /^분류된 근거 (\d+)건에 위험 신호가 없다/u.exec(r);
    if (m) return { text: one("reason_clean", Number(m[1])) };
  }
  return null;
}

/** 나라별 차이 문장에서 백엔드의 자리 표시("근거 부족: 확인되지 않음", "나라별 차이는 조사 중")는 문장이 아니므로 내지 않는다 */
export const isPlaceholder = (s: string | null | undefined) =>
  !s || /^근거 부족/u.test(s) || /^나라별 차이는 조사 중/u.test(s) || /^not (enough|confirmed)/iu.test(s) || /^insufficient/iu.test(s) || /^(still )?being (researched|investigated)/iu.test(s);

/** 나라별 차이의 '현지 밈' — 이름꼴인 것만(24자·세 낱말 이하, 해시태그·계정·문장 아님). 커뮤니티 문장이 섞여 들어온다. */
export function memeLabels(labels: string[], exclude: string[]): string[] {
  const ex = new Set(exclude.map(titleKey));
  const out: string[] = [];
  const seen = new Set<string>();
  for (const raw of labels) {
    const s = raw.trim();
    if (!s || s.length > 24 || s.split(/\s+/).length > 3 || /[#@\n「」『』“”"]/.test(s) || /[!?.]{2,}|…/.test(s)) continue;
    const k = titleKey(s);
    if (!k || ex.has(k) || seen.has(k)) continue;
    seen.add(k);
    out.push(s);
  }
  return out;
}

/* ── 지난 호 이후 달라진 것 ─────────────────────────────────────────────────
   최근 변화(7일)에서 이 판의 것만. 새로 실린 밈·뜻 바뀜은 대시보드 카드가 있고 그 지역이 이 판에 들 때, 검색 급증은 지역이 맞고 이유를 찾은 것만. */
export interface ChangeRow {
  kind: "verified" | "meaning_changed" | "spike";
  at: string;
  id: string | null;
  label: string;
  lang?: string;
  region?: string | null;
  lifecycle?: Lifecycle;
  risk?: "caution" | "avoid" | "unknown" | null;
  gloss?: string | null;
  glossLang?: string;
  previous?: string | null;
  reason?: string | null;
}

export function changeRows(items: UpdateRow[], edition: string, locale: Locale): ChangeRow[] {
  const scope = editionScope(edition);
  const out: ChangeRow[] = [];
  for (const i of items) {
    if (i.kind === "spike") {
      if (edition === "GLOBAL" || !i.region || !scope.has(i.region) || !i.reason) continue;
      out.push({ kind: "spike", at: i.at, id: null, label: i.label, lang: scriptLang(i.label, i.region), region: i.region, reason: i.reason[locale] || i.reason.ko || i.reason.en || null });
      continue;
    }
    if (i.kind !== "verified" && i.kind !== "meaning_changed") continue;
    const c = i.card;
    if (!c || !c.regions.some((r) => scope.has(r))) continue;
    const g = glossOf(c, locale);
    out.push({
      kind: i.kind, at: i.at, id: i.term_id ?? c.term_id, label: c.canonical, lang: c.lang, lifecycle: c.lifecycle, risk: riskOf(c),
      gloss: i.kind === "verified" ? g.text : null, glossLang: g.lang,
      previous: i.kind === "meaning_changed" && !isPlaceholder(i.previous) ? i.previous : null,
    });
  }
  return out;
}

/* ── 영상 썸네일 ── 유튜브 주소에 영상 id 가 있을 때만. 파일을 받아 두지 않고 유튜브가 주는 그림을 그대로 잇는다. */
export function youtubeId(url: string): string | null {
  const m = /(?:v=|shorts\/|youtu\.be\/|embed\/)([A-Za-z0-9_-]{11})(?![A-Za-z0-9_-])/.exec(url);
  return m ? m[1] : null;
}
export function videoThumb(evidences: { kind: string; url: string; title?: string | null }[]): { url: string; img: string; title: string } | null {
  for (const e of evidences) {
    if (e.kind !== "short") continue;
    const id = youtubeId(e.url);
    if (id) return { url: e.url, img: `https://i.ytimg.com/vi/${id}/mqdefault.jpg`, title: e.title ?? "" };
  }
  return null;
}
