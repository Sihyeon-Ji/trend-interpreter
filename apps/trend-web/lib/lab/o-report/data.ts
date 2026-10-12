/* 초안 1(/lab/o-report)의 서버 쪽 조립. lib/data.ts 의 함수만 부르고(읽기 전용), 화면에 필요한 칸만 골라 가볍게 넘긴다.
   판정(단계·쓸 때 조심·목록 나누기)은 백엔드 값 그대로이고, 여기서 새로 만드는 숫자는 검색 곡선에서 센 증감·순위뿐이다.
   부르는 수를 줄였다(09-29 검토: 첫 화면 한 번에 백엔드 약 150번). 곡선은 검색 정점이 있는 밈만, 사전 항목은 표지·고른 밈·
   읽기 도움이 필요한 줄만 받고, 한 번에 8개까지, 같은 갱신(보드 시각) 안에서는 다시 받지 않는다. 미리보기는 누를 때 받는다. */
import { getGenerationCurves, getKeywordBoard, getTermRecord, getTermSignals, getTermTopic, getUpdateFeed, getUpdatedAt, loadTermRecords } from "@/lib/data";
import { currentMeaning, headlineFor, textFor } from "@/lib/explain";
import type { LabLocale as Locale } from "@/lib/i18n";
import { riskOf } from "@/lib/keyword";
import { langTag, scriptLang } from "@/lib/lang";
import { L, sourceName, termLangLabel } from "@/lib/labels";
import { TARGET_REGIONS } from "@/lib/reader";
import { cleanSource } from "@/lib/sources";
import type { Evidence, KeywordBoard, KeywordCard, TermRecord } from "@/lib/types";
import type { GenerationCurve, Topic } from "@/lib/trends/types";
import type { Lifecycle } from "@/lib/contract/types";
import {
  align, dayIso, driverOf, genWindow, growthOf, hasHangul, indexOf, isStale, minDays, movingAverage, rankRows, readingOf, riskNotesOf, silhouette, weekly,
  type Aligned, type Change, type Driver, type Growth, type ListKey, type Media, type Preview, type RiskKey, type RiskNote, type Row, type Silhouette,
  type SortKey, type SourceRef, type Weeks,
} from "./index";

export const KNOWN_REGIONS = [...TARGET_REGIONS, "GLOBAL"];

/** ?regions=KR,JP → 알려진 코드만(칩 순서로). 없으면 한국, 'all' 이면 목표 지역 전체([]) */
export function parseRegions(raw: string | string[] | undefined): string[] {
  const v = [raw].flat().filter(Boolean).join(",");
  if (!v) return ["KR"];
  if (v === "all") return [];
  const asked = v.split(",").map((s) => s.trim().toUpperCase());
  const picked = KNOWN_REGIONS.filter((r) => asked.includes(r));
  return picked.length ? picked : ["KR"];
}

/* ───────── 부르는 수를 줄이는 도구 ───────── */

/** 한 번에 limit 개까지만 부른다 — 차가운 첫 화면에서 백엔드에 수십 개를 한꺼번에 던지지 않게 */
async function pool<T, R>(items: T[], limit: number, fn: (x: T) => Promise<R>): Promise<R[]> {
  const out = new Array<R>(items.length);
  let next = 0;
  const worker = async () => { while (next < items.length) { const i = next++; out[i] = await fn(items[i]); } };
  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, worker));
  return out;
}

/* 같은 갱신(보드 시각 하나) 동안 곡선과 다른 표기를 기억한다 — 곡선은 파이프라인이 돌 때만 바뀐다. 실패(빈 값)는 기억하지 않는다. */
const run = { at: "", curves: new Map<string, GenerationCurve[]>(), aliases: new Map<string, string[]>() };
function memoFor(at: string) {
  if (run.at !== at) { run.at = at; run.curves.clear(); run.aliases.clear(); }
  return run;
}

async function curvesFor(ids: string[], at: string): Promise<Map<string, GenerationCurve[]>> {
  const memo = memoFor(at);
  const need = ids.filter((id) => !memo.curves.has(id));
  await pool(need, 8, async (id) => {
    const c = await getGenerationCurves(id).catch(() => [] as GenerationCurve[]);
    if (c.length) memo.curves.set(id, c);
  });
  return new Map(ids.map((id) => [id, memo.curves.get(id) ?? []]));
}

async function recordsFor(ids: string[], at: string): Promise<Map<string, TermRecord | null>> {
  const memo = memoFor(at);
  const got = await pool(ids, 8, async (id) => {
    try {
      const r = await getTermRecord(id);
      memo.aliases.set(id, r?.term.aliases ?? []);
      return [id, r] as const;
    } catch {
      return [id, null] as const;
    }
  });
  return new Map(got);
}

/* ───────── 보이는 출처 (사용자 결정 09-29): 위키·기사·영상만. 커뮤니티·SNS 글은 제목·인용·사이트 이름을 내지 않는다 ───────── */

const WIKI = /(^|\.)(wikipedia\.org|wiktionary\.org|namu\.wiki|knowyourmeme\.com|pixiv\.net)$/i;
const UGC = new Set([
  "브런치", "brunch.co.kr", "weverse", "디시인사이드", "갤러리", "더쿠", "theqoo", "theqoo.net", "인스티즈", "instiz", "instiz.net",
  "에펨코리아", "fmkorea", "루리웹", "ruliweb", "클리앙", "clien", "뽐뿌", "ppomppu", "reddit", "reddit.com", "bsky.app", "bluesky",
  "news.ycombinator.com", "hacker news", "5ch.net", "pantip.com", "dcard.tw", "girlschannel.net", "togetter.com", "naver:blog",
  "naver:cafearticle", "naver:kin", "lemmy", "x.com", "twitter.com", "instagram.com", "threads.net", "facebook.com", "tiktok.com",
]);
const UGC_HOST = /(^|\.)(dcinside\.com|theqoo\.net|instiz\.net|fmkorea\.com|ruliweb\.com|clien\.net|ppomppu\.co\.kr|reddit\.com|bsky\.app|ycombinator\.com|5ch\.net|pantip\.com|dcard\.tw|brunch\.co\.kr|weverse\.io|cafe\.naver\.com|kin\.naver\.com|blog\.naver\.com)$/i;

function host(url: string): string {
  try { return new URL(url).hostname.toLowerCase(); } catch { return ""; }
}
function hasPath(url: string): boolean {
  try { return !["", "/"].includes(new URL(url).pathname); } catch { return false; }
}

export function youtubeId(url: string): string | null {
  if (!/youtu\.?be/.test(url)) return null;
  const m = /(?:v=|shorts\/|youtu\.be\/|embed\/)([A-Za-z0-9_-]{6,20})/.exec(url);
  return m ? m[1] : null;
}

type Visible = "wiki" | "news" | "video";

/** 커뮤니티·SNS 글인가 — 건수로만 밝힌다 */
function isCommunity(e: Pick<Evidence, "kind" | "source_domain" | "url">): boolean {
  if (e.kind === "community") return true;
  if (e.kind !== "news" && e.kind !== "web") return false;
  return UGC.has((e.source_domain ?? "").toLowerCase()) || UGC_HOST.test(host(e.url));
}

/** 화면에 보여도 되는 근거인가, 그렇다면 어떤 종류로. 첫 화면 주소뿐인 근거(https://youtube.com/ 같은 것)는
 *  눌러도 그 글로 가지 않으므로 내지 않는다 — 확인할 수 없는 출처를 근거처럼 보이지 않게. */
export function visibleKind(e: Pick<Evidence, "kind" | "source_domain" | "url">): Visible | null {
  if (!hasPath(e.url)) return null;
  if (e.kind === "short") return "video";   // 쇼츠 영상은 보인다(영상 댓글·글은 community 종류로 따로 온다)
  const dom = (e.source_domain ?? "").toLowerCase();
  if (UGC.has(dom) || UGC_HOST.test(host(e.url))) return null;
  if (e.kind === "wiki") return "wiki";
  if (e.kind === "web") return WIKI.test(dom) || WIKI.test(host(e.url)) ? "wiki" : null;
  if (e.kind === "news") return "news";
  return null;
}

/* 앱의 sourceName 에 없는 이름 */
const NEWS_NAME: Record<string, { ko: string; en: string }> = {
  "n.news.naver.com": { ko: "네이버 뉴스", en: "Naver News" },
  "news.naver.com": { ko: "네이버 뉴스", en: "Naver News" },
  "v.daum.net": { ko: "다음 뉴스", en: "Daum News" },
  "news.yahoo.co.jp": { ko: "야후! 뉴스", en: "Yahoo! News" },
  "ko.wiktionary.org": { ko: "위키낱말사전", en: "Korean Wiktionary" },
  "en.wiktionary.org": { ko: "영어 위키낱말사전", en: "English Wiktionary" },
  "ja.wiktionary.org": { ko: "일본어 위키낱말사전", en: "Japanese Wiktionary" },
  "zh.wiktionary.org": { ko: "중국어 위키낱말사전", en: "Chinese Wiktionary" },
  "knowyourmeme.com": { ko: "Know Your Meme", en: "Know Your Meme" },
};
/* 언어판 위키백과 — 앱의 이름 표에 없는 판(id·th·vi …)은 '인도네시아어 위키백과' 처럼 짓는다 */
function wikiName(domain: string, locale: Locale): string | null {
  const m = /^([a-z]{2,3})\.(?:m\.)?wikipedia\.org$/.exec(domain);
  if (!m) return null;
  const lang = termLangLabel(locale, m[1]);
  if (lang === m[1]) return null;
  return locale === "ko" ? `${lang} 위키백과` : `${lang} Wikipedia`;
}
const nameOf = (domain: string, locale: Locale) => {
  const known = NEWS_NAME[domain]?.[locale] ?? sourceName(locale, domain);
  return known !== domain ? known : wikiName(domain, locale) ?? domain;
};

/* 같은 기사가 여러 포털에 실린 것(야후! 뉴스·야후! 파이낸스·원래 언론사)은 한 번만 — 원래 언론사를 남긴다(09-29 검토: 推し活 출처에 같은 제목 셋) */
const AGGREGATOR = /^(yahoo!?\s*(ニュース|ファイナンス|news|finance|奇摩)?|msn|smartnews|line\s*news|네이버\s*뉴스|다음\s*뉴스|naver\s*news|daum\s*news|google\s*news)$/i;
const squash = (s: string) => s.toLowerCase().normalize("NFKC").replace(/[^\p{L}\p{N}]+/gu, "");
/** 제목 비교용 — 끝의 '(매체 이름)' 과 문장부호·공백 차이를 없앤다 */
const titleKey = (t: string) => squash(t.normalize("NFKC").replace(/[(（][^()（）]{1,40}[)）]\s*$/, ""));
const urlKey = (url: string) => {
  try {
    const u = new URL(url);
    return `${u.hostname.replace(/^(www|m)\./, "")}${decodeURIComponent(u.pathname).replace(/[\s_]+/g, "_").replace(/\/$/, "")}${u.search}`.toLowerCase();
  } catch { return url; }
};
const pageName = (url: string) => { try { return decodeURIComponent(new URL(url).pathname.split("/").filter(Boolean).at(-1) ?? ""); } catch { return ""; } };
const escapeRe = (x: string) => x.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/** 기사 제목 끝의 ' - 매체 이름' 을 떼고, 그 이름이 출처 칸의 이름과 같으면 제대로 쓴 이름(대소문자·띄어쓰기)을 돌려준다 */
function splitTail(title: string, domain: string): { title: string; publisher: string | null } {
  const at = title.lastIndexOf(" - ");
  if (at < 0) return { title, publisher: null };
  const tail = title.slice(at + 3).trim();
  const d = squash(domain), t = squash(tail);
  return t && d && (t === d || d.startsWith(t) || t.startsWith(d)) ? { title: title.slice(0, at).trim(), publisher: tail } : { title, publisher: null };
}

interface Candidate { ref: SourceRef; named: boolean; aggregator: boolean; tkey: string; ukey: string }

function candidateOf(e: Evidence, names: string[], locale: Locale): Candidate | null {
  const kind = visibleKind(e);
  if (!kind) return null;
  // 제목 끝의 ' - 매체 이름' 은 다듬기 전의 원래 제목에서 읽는다(대소문자·띄어쓰기가 살아 있는 이름: 'スポニチ Sponichi Annex')
  const tail = kind === "news" ? splitTail((e.title ?? "").trim(), e.source_domain) : { title: e.title ?? "", publisher: null };
  const row = cleanSource({ ...e, title: tail.title }, names[0] ?? "", locale);
  // 네이버 뉴스 검색으로 들어온 기사는 주소가 곧 언론사다 — '네이버 뉴스' 대신 언론사 주소를 적는다
  const naverNews = e.source_domain === "naver:news" && !/(^|\.)naver\.com$/.test(host(e.url));
  const src = naverNews ? host(e.url).replace(/^(www|m|news|n|mobile)\./, "") : tail.publisher ?? nameOf(e.source_domain, locale);
  // 수집기가 제목 앞에 붙인 출처 이름("네이버 뉴스 · …", "Wikipedia: …")을 뗀다 — 출처 칸에 이미 있다
  const prefixes = [src, sourceName("ko", e.source_domain), "네이버 뉴스", "Naver News", "Wikipedia", "위키백과", "나무위키"];
  const hit = prefixes.find((x) => x && new RegExp(`^${escapeRe(x)}\\s*[·|:：–-]\\s*`, "i").test(row.title));
  const title = (hit ? row.title.replace(new RegExp(`^${escapeRe(hit)}\\s*[·|:：–-]\\s*`, "i"), "") : row.title) || row.title;
  const keys = names.map(squash).filter(Boolean);
  const page = squash(pageName(e.url));
  return {
    ref: { name: src, nameLang: scriptLang(src), title, titleLang: scriptLang(title), url: e.url, date: e.observed_at, kind },
    named: kind === "wiki" && keys.some((k) => squash(title).includes(k) || (page.length > 0 && page.includes(k))),
    aggregator: kind === "news" && AGGREGATOR.test(src.trim()),
    tkey: `${kind === "wiki" ? "w" : "n"}:${titleKey(title)}`,
    ukey: urlKey(e.url),
  };
}

/** 출처 목록. 참고 위키(이 밈 이름의 문서 먼저) → 기사·영상(최근 먼저). 같은 주소·같은 제목은 한 번만, 포털 사본보다 원래 언론사. */
export function sourceList(evidences: Evidence[], names: string[], locale: Locale): SourceRef[] {
  const cands = evidences.map((e) => candidateOf(e, names, locale)).filter((c): c is Candidate => !!c);
  const byTitle = new Map<string, Candidate>();
  const seenUrl = new Set<string>();
  // 같은 주소가 위키 수집(wiki)과 검색(web)으로 두 번 들어오면 먼저 온 쪽만
  for (const c of [...cands].sort((a, b) => b.ref.date.localeCompare(a.ref.date))) {
    if (seenUrl.has(c.ukey)) continue;
    seenUrl.add(c.ukey);
    const key = c.tkey.length > 4 ? c.tkey : c.ukey;
    const was = byTitle.get(key);
    if (!was || (was.aggregator && !c.aggregator)) byTitle.set(key, c);
  }
  const rank = (c: Candidate) => (c.ref.kind === "wiki" ? (c.named ? 0 : 1) : 2);
  return [...byTitle.values()].sort((a, b) => rank(a) - rank(b) || b.ref.date.localeCompare(a.ref.date)).map((c) => c.ref);
}

/** 유래 옆에 붙일 근거 둘 — 이 밈 이름의 위키 문서, 없으면 다른 위키 문서, 그것도 없으면 가장 먼저 나온 기사 */
function originRefs(list: SourceRef[], names: string[]): SourceRef[] {
  const keys = names.map(squash).filter(Boolean);
  const wikis = list.filter((s) => s.kind === "wiki");
  const named = wikis.filter((s) => keys.some((k) => squash(s.title).includes(k)));
  const pick = named.length ? named : wikis.length ? wikis : list.filter((s) => s.kind === "news").sort((a, b) => a.date.localeCompare(b.date));
  const out: SourceRef[] = [];
  for (const s of pick) if (out.length < 2 && !out.some((o) => o.name === s.name)) out.push(s);
  return out;
}

function mediaOf(r: TermRecord): Media | null {
  const img = (r.media ?? []).find((m) => m.kind === "image");
  if (img) return { kind: "image", src: img.url, href: img.page_url, title: img.title, license: img.license, attribution: img.attribution };
  const vid = (r.media ?? []).find((m) => m.kind === "video" && youtubeId(m.url));
  if (vid) {
    const id = youtubeId(vid.url)!;
    return { kind: "video", src: `https://i.ytimg.com/vi/${id}/mqdefault.jpg`, href: `https://www.youtube.com/watch?v=${id}`, title: vid.title };
  }
  const short = r.evidences.find((e) => e.kind === "short" && youtubeId(e.url));
  if (short) {
    const id = youtubeId(short.url)!;
    return { kind: "video", src: `https://i.ytimg.com/vi/${id}/mqdefault.jpg`, href: `https://www.youtube.com/watch?v=${id}`, title: short.title ?? "" };
  }
  return null;
}

const namesOf = (r: TermRecord) => [r.term.canonical, ...(r.term.aliases ?? [])];

export function previewOf(r: TermRecord, locale: Locale): Preview {
  const tx = textFor(r, locale);
  const textLang = locale === "en" && !r.en ? "ko" : undefined;
  // 유래 칸에 도메인만 들어온 자료(“wikipedia.org”)는 유래가 아니다
  const origin = tx?.origin && tx.origin !== "unknown" && !/^[a-z0-9.-]+\.[a-z]{2,}$/i.test(tx.origin.trim()) ? tx.origin : null;
  return {
    id: r.term.term_id,
    aliases: (r.term.aliases ?? []).filter((a) => a && a.toLowerCase() !== r.term.canonical.toLowerCase()).slice(0, 4),
    definition: tx ? headlineFor(tx, locale) : null,
    origin,
    nuance: tx?.nuance && tx.nuance !== "unknown" ? tx.nuance : null,
    plain: tx?.plain || null,
    textLang,
    refs: originRefs(sourceList(r.evidences, namesOf(r), locale), namesOf(r)),
    verified: r.term.status === "verified",
    media: mediaOf(r),
  };
}

/** 미리보기 경로(누를 때 받는다). 없으면 null, 서버가 답하지 않으면 던진다 */
export async function loadPreview(termId: string, locale: Locale): Promise<Preview | null> {
  const r = await getTermRecord(termId);
  return r ? previewOf(r, locale) : null;
}

/* ───────── 리포트(첫 화면) ───────── */

interface Stat { a: Aligned | null; growth: Growth | null; prev: Growth | null; stale: boolean; index: number[] | null }
const NO_STAT: Stat = { a: null, growth: null, prev: null, stale: false, index: null };

function statOf(curves: GenerationCurve[] | undefined, weeks: Weeks, boardAt: string): Stat {
  const a = curves?.length ? align(curves) : null;
  if (!a) return NO_STAT;
  const stale = isStale(a, boardAt);
  if (stale) return { ...NO_STAT, a, stale };
  const w = weeks * 7;
  const growth = growthOf(a, w);
  // 순위 변화는 4주 창만 — 12주는 세 창(252일)이 곡선 길이(180일)보다 길다
  const prev = weeks === 4 ? growthOf(a, w, w) : null;
  return { a, growth, prev, stale, index: growth.value != null ? indexOf(a, growth.used) : null };
}

function thumbOf(c: KeywordCard): Row["thumb"] {
  const e = c.evidences.find((x) => x.kind === "short" && youtubeId(x.url));
  if (!e) return null;
  const id = youtubeId(e.url)!;
  return { src: `https://i.ytimg.com/vi/${id}/mqdefault.jpg`, href: `https://www.youtube.com/watch?v=${id}`, title: e.title };
}

function rowOf(c: KeywordCard, s: Stat, weeks: Weeks, locale: Locale, searchable: boolean): Row {
  const gloss = locale === "en" ? c.gloss_en || c.gloss_ko : c.gloss_ko || c.gloss_en;
  const show = searchable && !!s.a && !s.stale;
  const growth = show ? s.growth?.value ?? null : null;
  return {
    id: c.term_id,
    name: c.canonical,
    lang: langTag(c.lang),
    reading: null,
    gloss,
    glossLang: locale === "en" && !c.gloss_en ? "ko" : undefined,
    lifecycle: c.lifecycle,
    diffusion: c.diffusion ?? null,
    risk: riskOf(c),
    riskNotes: riskNotesOf(c.risk_reasons, locale),
    regions: c.regions,
    growth,
    rank: null,
    rankChange: null,
    searched: show,
    // 셀 수 없는 밈은 선도 그리지 않는다. 선은 증감을 센 연령대의 평균이다(그림과 숫자가 같은 자료)
    spark: growth != null && s.index ? weekly(s.index).map((v) => Math.round(v * 10) / 10) : null,
    sparkRecent: weeks,
    lastUsed: c.last_used ?? null,
    thumb: thumbOf(c),
  };
}

/** 사전 항목의 대표 영상(유튜브)도 표지 그림으로 쓴다 — 썸네일 주소만, 파일은 받지 않는다.
 *  사진(위키미디어)은 저작자 표시가 필요해 표지에 쓰지 않고, 표시를 함께 다는 미리보기·항목 화면에서만 보인다. */
const videoThumb = (m: Media | null | undefined): Row["thumb"] => (m?.kind === "video" ? { src: m.src, href: m.href, title: m.title } : null);

export interface SpotItem { row: Row; shape: Silhouette | null; driver: Driver | null }

export interface Report {
  generatedAt: string;
  regions: string[];              // 백엔드가 실제로 고른 지역 (전체면 목표 지역 10곳)
  asked: string[];                // 주소에 적힌 지역 ([] = 전체)
  counts: Record<string, number>;
  totals: KeywordBoard["totals"];
  known: number;                  // 고른 지역에서 확인된 밈 수 (쓰이는 + 식는 + 사용 자제 — 칩 건수와 같은 규칙)
  avoidOnly: number;              // 사용 자제 밈 수 (쓰이는·식는 목록이 비었을 때 빈 화면이 이유를 말한다)
  page: number;
  pageSize: number;
  searchable: boolean;            // 한국이 들어 있어 네이버 검색 곡선을 쓸 수 있나
  lists: { rising: Row[]; fading: Row[]; caution: Row[] };   // 백엔드 순서 그대로. 순위(rank)는 쓰이는 밈에만 매겨 둔다
  ranked: number;                 // 쓰이는 밈 가운데 순위를 매긴 수
  previews: Record<string, Preview>;   // 처음 고른 밈 하나만
  selectedId: string | null;
  spotlight: { mode: "growth" | "plain" | "flat"; items: SpotItem[] };
  changes: Change[];
  spikes: number;                 // 고른 지역의 최근 7일 검색 급증 수 (빈 지역의 다음 할 일)
  dataRange: { from: string; to: string } | null;
}

export interface Selection { tab: ListKey; sort: SortKey; m: string | null }

/** 표에서 처음 고를 밈 — 주소에 있으면 그것, 없으면 지금 탭·정렬의 첫 줄(지켜보는 밈 탭은 브라우저가 정한다) */
function firstRow(lists: Report["lists"], pick: Selection): string | null {
  if (pick.m) return pick.m;
  if (pick.tab === "watch") return null;
  const rows = lists[pick.tab];
  if (pick.tab === "rising" && pick.sort === "gain") return (rows.filter((r) => r.rank != null).sort((a, b) => a.rank! - b.rank!)[0] ?? rows[0])?.id ?? null;
  return rows[0]?.id ?? null;
}

export async function loadReport(asked: string[], weeks: Weeks, page: number, locale: Locale, pick: Selection): Promise<Report> {
  const first = await getKeywordBoard(asked, 1);   // 실패하면 던진다 → error.tsx
  const at = first.generated_at;
  const size = first.page_size || 30;
  // '쓰이는 밈' 은 순위를 매기려고 끝까지 받는다(30개가 넘는 경우는 전체 지역 33개 정도)
  const risingPages = Math.min(4, Math.ceil(first.totals.rising / size));
  const last = Math.max(1, Math.ceil(Math.max(first.totals.fading, first.totals.caution) / size));
  const p = Math.min(Math.max(1, page), last);
  const pagesToGet = [...new Set([...Array.from({ length: Math.max(0, risingPages - 1) }, (_, i) => i + 2), ...(p > 1 ? [p] : [])])];
  const [boards, feed] = await Promise.all([
    Promise.all(pagesToGet.map((n) => getKeywordBoard(asked, n).then((b) => [n, b] as const).catch(() => [n, null] as const))),
    getUpdateFeed(168).catch(() => null),
  ]);
  const byPage = new Map<number, KeywordBoard | null>([[1, first], ...boards]);
  const rising = [...first.rising, ...Array.from({ length: Math.max(0, risingPages - 1) }, (_, i) => byPage.get(i + 2)?.rising ?? []).flat()];
  const other = byPage.get(p) ?? first;
  const fading = other.fading, caution = other.caution;

  const regions = first.regions;
  const searchable = regions.includes("KR");
  const cards = new Map<string, KeywordCard>();
  for (const c of [...rising, ...fading, ...caution]) if (!cards.has(c.term_id)) cards.set(c.term_id, c);

  // 곡선은 검색 정점이 있는(네이버에서 검색된) 밈만 — 나머지는 곡선이 없다
  const withCurves = searchable ? [...cards.values()].filter((c) => (c.gen_peaks?.length ?? 0) > 0).map((c) => c.term_id) : [];
  const curves = await curvesFor(withCurves, at);
  const stats = new Map([...cards.keys()].map((id) => [id, statOf(curves.get(id), weeks, at)]));

  const toRow = (c: KeywordCard) => rowOf(c, stats.get(c.term_id) ?? NO_STAT, weeks, locale, searchable);
  const risingRows = rising.map((c) => ({ ...toRow(c), prevGrowth: searchable ? stats.get(c.term_id)?.prev?.value ?? null : null }));
  const rankedRising = rankRows(risingRows).map(({ row, rank, rankChange }) => { const { prevGrowth, ...r } = row; void prevGrowth; return { ...r, rank, rankChange } as Row; });
  let lists = { rising: rankedRising, fading: fading.map(toRow), caution: caution.map(toRow) };

  // 이번 주 주목: 검색이 늘어난 밈 셋(늘어난 순). 검색 자료가 없는 지역은 백엔드 순서의 셋(늘었다고 말하지 않는다)
  const byRank = rankedRising.filter((r) => r.rank != null).sort((a, b) => a.rank! - b.rank!);
  const up = byRank.filter((r) => (r.growth ?? 0) > 0).slice(0, 3);
  const mode: Report["spotlight"]["mode"] = up.length ? "growth" : searchable && byRank.length ? "flat" : "plain";
  const spotRows = mode === "growth" ? up : mode === "plain" ? rankedRising.slice(0, 3) : [];

  // 사전 항목은 필요한 것만: 표지(읽기 도움·대표 영상), 처음 고른 밈(미리보기), 한국어 화면에서 한글이 없는 이름(읽기 도움)
  const selectedId = firstRow(lists, pick);
  const memo = memoFor(at);
  const readingIds = locale === "ko" ? [...cards.values()].filter((c) => !hasHangul(c.canonical) && !memo.aliases.has(c.term_id)).map((c) => c.term_id) : [];
  const recordIds = [...new Set([...spotRows.map((r) => r.id), ...(selectedId ? [selectedId] : []), ...readingIds])];
  const records = await recordsFor(recordIds, at);
  const aliasesOf = (id: string) => records.get(id)?.term.aliases ?? memo.aliases.get(id) ?? [];

  const withReading = (r: Row, always = false): Row => {
    if (locale !== "ko" && !always) return r;
    const reading = readingOf(r.name, aliasesOf(r.id), locale);
    return reading ? { ...r, reading, readingLang: locale === "ko" ? "ko" : undefined } : r;
  };
  lists = { rising: lists.rising.map((r) => withReading(r)), fading: lists.fading.map((r) => withReading(r)), caution: lists.caution.map((r) => withReading(r)) };

  const labels = L(locale).generation;
  const spotlight = {
    mode,
    items: spotRows.map((r0) => {
      const rec = records.get(r0.id) ?? null;
      const row = withReading({ ...(lists.rising.find((x) => x.id === r0.id) ?? r0), thumb: r0.thumb ?? videoThumb(rec ? mediaOf(rec) : null) }, true);
      const s = stats.get(row.id) ?? NO_STAT;
      const d = mode === "growth" && s.growth ? driverOf(s.growth) : null;
      return {
        row,
        shape: mode === "growth" && s.index ? silhouette(s.index, weeks * 7, weeks === 4 ? 2 : 3) : null,
        driver: d ? { gen: d.gen, label: labels[d.gen as keyof typeof labels] ?? d.gen, change: d.change } : null,
      };
    }),
  };

  const previews: Record<string, Preview> = {};
  const sel = selectedId ? records.get(selectedId) : null;
  if (sel) previews[sel.term.term_id] = previewOf(sel, locale);

  const ends = [...stats.values()].filter((s) => s.a && !s.stale && s.growth?.value != null).map((s) => s.a!.end);
  const dataRange = searchable && ends.length ? { from: dayIso(Math.min(...ends)), to: dayIso(Math.max(...ends)) } : null;
  const changes = changesFor(feed?.items ?? [], regions, locale);
  const avoidOnly = first.caution.filter((c) => c.risk_level === "avoid").length;

  return {
    generatedAt: at,
    regions,
    asked,
    counts: first.counts,
    totals: first.totals,
    known: asked.length === 1 ? first.counts[asked[0]] ?? 0 : asked.length === 0 ? first.counts.ALL ?? 0 : first.totals.rising + first.totals.fading + avoidOnly,
    avoidOnly,
    page: p,
    pageSize: size,
    searchable,
    lists,
    ranked: byRank.length,
    previews,
    selectedId,
    spotlight,
    changes,
    spikes: changes.filter((c) => c.kind === "spike").length,
    dataRange,
  };
}

/** 최근 7일 변화 가운데 고른 지역의 것만. 새 밈·뜻 바뀜은 대시보드 카드가 있는(둘러보는 목록에 있는) 밈만 */
function changesFor(items: NonNullable<Awaited<ReturnType<typeof getUpdateFeed>>>["items"], regions: string[], locale: Locale): Change[] {
  const want = new Set(regions);
  const out: Change[] = [];
  for (const i of items) {
    if (i.kind === "spike") {
      if (!i.region || !want.has(i.region)) continue;
      const note = i.reason ? (locale === "en" ? i.reason.en || i.reason.ko : i.reason.ko || i.reason.en) : null;
      // 이유 문장은 백엔드가 쓴 말 그대로라 일본어가 섞여 온다 — 글자로 말을 짐작해 lang 을 단다
      out.push({ kind: "spike", at: i.at, id: null, label: i.label, lang: scriptLang(i.label, i.region), region: i.region, note, noteLang: note ? scriptLang(note, i.region) : undefined });
      continue;
    }
    if (i.kind !== "verified" && i.kind !== "meaning_changed") continue;
    const c = i.card;
    if (!c || !c.regions.some((r) => want.has(r))) continue;
    const gloss = locale === "en" ? c.gloss_en || c.gloss_ko : c.gloss_ko || c.gloss_en;
    out.push({
      kind: i.kind, at: i.at, id: i.term_id ?? c.term_id, label: c.canonical, lang: langTag(c.lang), region: null,
      note: i.kind === "meaning_changed" ? i.previous ?? null : gloss,
      noteLang: i.kind === "meaning_changed" || (locale === "en" && !c.gloss_en) ? "ko" : undefined,
    });
  }
  return out.slice(0, 200);
}

/* ───────── 지켜보는 밈의 지금 상태 (지금 목록에 없는 것만 브라우저가 묻는다) ───────── */

export interface WatchState {
  id: string;
  gone: boolean;                 // 사전에서 빠졌다
  lifecycle?: Lifecycle;
  risk?: RiskKey;
  regions?: string[];
  gloss?: string;
  glossLang?: string;
}

export async function loadWatchStates(ids: string[], locale: Locale): Promise<WatchState[]> {
  const got = await pool(ids.slice(0, 60), 6, async (id): Promise<WatchState | null> => {
    const card = await getTermSignals(id).catch(() => null);
    if (card) {
      const gloss = locale === "en" ? card.gloss_en || card.gloss_ko : card.gloss_ko || card.gloss_en;
      return { id, gone: false, lifecycle: card.lifecycle, risk: riskOf(card) ?? "none", regions: card.regions, gloss, glossLang: locale === "en" && !card.gloss_en ? "ko" : undefined };
    }
    try {
      const r = await getTermRecord(id);
      if (!r) return { id, gone: true };
      const tx = textFor(r, locale);
      return { id, gone: false, lifecycle: r.term.lifecycle ?? "unknown", risk: riskOf(r.term) ?? "none", regions: currentMeaning(r)?.regions ?? [], gloss: tx?.definition ?? "", glossLang: locale === "en" && !r.en ? "ko" : undefined };
    } catch {
      return null;   // 서버가 답하지 않으면 모른다고 둔다('빠졌다' 고 하지 않는다)
    }
  });
  return got.filter((x): x is WatchState => !!x);
}

/* ───────── 밈 항목 ───────── */

export interface GenLine {
  gen: string;
  label: string;
  weeklyValues: number[];
  peak: string | null;
  growth: number | null;         // 이 연령대의 4주 증감 (자료가 넉넉할 때만)
  used: boolean;                 // 연령대 평균·증감에 넣었나
  recentAvg: number | null;      // 최근 4주 하루 평균 지수 (표로 보기)
  baseAvg: number | null;
  daysRecent: number;            // 최근 4주 가운데 검색이 있던 날
  daysBase: number;
}

export interface EntryTrend {
  start: string;
  end: string;
  daily: number[];               // 7일 평균 — 증감을 센 연령대의 평균(셀 수 없으면 모든 연령대)
  averaged: string[];            // 위 평균에 넣은 연령대 이름
  growth4: number | null;
  growth12: number | null;
  stale: boolean;
  minDays: number;               // 4주 창마다 검색이 있어야 하는 날
  gens: GenLine[];
}

export interface Variant { region: string; regionLabel: string; local: string; localLang?: string; diff: string | null; diffLang?: string; memes: { label: string; lang?: string }[] }

export interface HistoryItem { from: string; to: string | null; definition: string; current: boolean }

export interface Entry {
  id: string;
  name: string;
  lang?: string;
  preview: Preview;
  lifecycle: NonNullable<TermRecord["term"]["lifecycle"]>;
  diffusion: TermRecord["term"]["diffusion"];
  risk: ReturnType<typeof riskOf>;
  riskNotes: RiskNote[];
  regions: string[];
  lastUsed: string | null;       // 고른 지역에서 마지막으로 쓰인 때 — 검색 곡선이 없는 표지에 선다
  canMake: boolean;
  firstAdded: string | null;
  sources: SourceRef[];
  communityCount: number;
  trend: EntryTrend | null;
  variants: Variant[];
  history: HistoryItem[];
  updatedAt: string | null;
}

function trendOf(curves: GenerationCurve[], boardAt: string | null, locale: Locale): EntryTrend | null {
  const a = align(curves);
  if (!a || a.end - a.start + 1 < 14) return null;
  const stale = !!boardAt && isStale(a, boardAt);
  const labels = L(locale).generation;
  const g4 = stale ? null : growthOf(a, 28);
  const g12 = stale ? null : growthOf(a, 84);
  const averagedGens = g4?.value != null ? g4.used : a.gens.map((g) => g.gen);
  const gens = a.gens.map((g): GenLine => {
    const x = genWindow(g.values, 28);
    return {
      gen: g.gen,
      label: labels[g.gen as keyof typeof labels] ?? g.gen,
      weeklyValues: weekly(g.values).map((v) => Math.round(v * 10) / 10),
      peak: g.peak,
      growth: g4?.byGen[g.gen] ?? null,
      used: averagedGens.includes(g.gen),
      recentAvg: x ? Math.round((x.recent / 28) * 10) / 10 : null,
      baseAvg: x ? Math.round((x.base / 28) * 10) / 10 : null,
      daysRecent: x?.daysRecent ?? 0,
      daysBase: x?.daysBase ?? 0,
    };
  });
  return {
    start: dayIso(a.start),
    end: dayIso(a.end),
    daily: movingAverage(indexOf(a, averagedGens)).map((v) => Math.round(v * 10) / 10),
    averaged: averagedGens.map((g) => labels[g as keyof typeof labels] ?? g),
    growth4: g4?.value ?? null,
    growth12: g12?.value ?? null,
    stale,
    minDays: minDays(28),
    gens,
  };
}

/* 나라별 차이의 '아직 모른다' 는 차이가 아니다 — 자리 채움 문장은 내지 않는다(근거 부족·조사 중·구체적인 정보 없음) */
const NO_FINDING = /^(근거 부족|나라별 차이는 조사 중|근거에 .{0,40}(정보|언급)(는|은|이|가)? 없습니다\.?$|insufficient evidence|country differences are still being researched)/i;
/* 그곳에서 생긴 말 칸에 SNS 계정(@…bsky.social)·사이트 주소가 섞여 온다 — 커뮤니티 글의 계정·사이트 이름은 내지 않는다(09-29 결정) */
const NOT_A_MEME = /^@|https?:\/\/|(^|\.)[a-z0-9-]+\.(social|com|net|org|app|io|co|kr|jp|au|tw|hk|th|vn|id|ph|my|sg)(\.[a-z]{2})?$/i;

function variantsOf(topic: Topic | null, locale: Locale): Variant[] {
  if (!topic) return [];
  const labels = L(locale).region;
  return topic.variants
    .filter((v) => v.region && labels[v.region])
    .map((v) => {
      const raw = ((locale === "en" ? v.what_changed.en || v.what_changed.ko : v.what_changed.ko || v.what_changed.en) ?? "").trim();
      const diff = raw && !NO_FINDING.test(raw) ? raw : null;
      return {
        region: v.region,
        regionLabel: labels[v.region],
        local: v.local_name,
        localLang: scriptLang(v.local_name, v.region),
        diff,
        diffLang: locale === "en" && !v.what_changed.en && diff ? "ko" : undefined,
        memes: v.local_memes.filter((m) => m.label && m.label !== v.local_name && !NOT_A_MEME.test(m.label.trim())).slice(0, 4).map((m) => ({ label: m.label, lang: scriptLang(m.label, v.region) })),
      };
    })
    .filter((v) => v.diff || v.memes.length);
}

export async function loadEntry(termId: string, regions: string[], locale: Locale): Promise<Entry | null> {
  const record = await getTermRecord(termId);   // 서버가 답하지 않으면 던진다 → error.tsx, 없으면 null
  if (!record) return null;
  const [curves, signals, topic, updatedAt] = await Promise.all([
    getGenerationCurves(termId).catch(() => []),
    getTermSignals(termId, regions).catch(() => null),
    getTermTopic(termId, record.term.canonical).catch(() => null),
    getUpdatedAt().catch(() => null),
  ]);
  const term = record.term;
  const preview = previewOf(record, locale);
  const cur = currentMeaning(record);
  const verified = term.status === "verified";
  const history = [...record.meanings]
    .filter((m) => m.verification === "verified_auto" || m.verification === "verified_human")
    .sort((a, b) => b.valid_from.localeCompare(a.valid_from))
    .map((m) => ({ from: m.valid_from, to: m.valid_to ?? null, definition: m.definition, current: m === cur || !m.valid_to }));
  const risk = riskOf(term);
  return {
    id: term.term_id,
    name: term.canonical,
    lang: langTag(term.lang),
    preview,
    lifecycle: term.lifecycle ?? "unknown",
    diffusion: term.diffusion ?? null,
    risk,
    riskNotes: riskNotesOf(term.risk_reasons ?? [], locale),
    regions: signals?.regions?.length ? signals.regions : cur?.regions ?? [],
    lastUsed: signals?.last_used ?? null,
    canMake: verified && term.risk_level !== "avoid",
    firstAdded: history.at(-1)?.from ?? null,
    sources: sourceList(record.evidences, namesOf(record), locale).slice(0, 12),
    communityCount: record.evidences.filter(isCommunity).length,
    trend: trendOf(curves, updatedAt, locale),
    variants: variantsOf(topic, locale),
    history,
    updatedAt,
  };
}

/* ───────── 찾기 색인 (프레임의 찾기 칸이 처음 쓸 때 받고, 사전 화면이 쓴다) ───────── */

export interface IndexItem { id: string; name: string; lang?: string; aliases: string[]; gloss: string; glossLang?: string; risk: ReturnType<typeof riskOf>; lifecycle: Lifecycle }

export async function loadSearchIndex(locale: Locale): Promise<IndexItem[] | null> {
  const { records, ok } = await loadTermRecords();
  if (!ok) return null;
  return records.filter((r) => r.term.status === "verified").map((r) => {
    const tx = textFor(r, locale);
    return {
      id: r.term.term_id,
      name: r.term.canonical,
      lang: langTag(r.term.lang),
      aliases: (r.term.aliases ?? []).slice(0, 4),
      gloss: (tx?.plain || tx?.definition || "").slice(0, 90),
      glossLang: locale === "en" && !r.en ? "ko" : undefined,
      risk: riskOf(r.term),
      lifecycle: r.term.lifecycle ?? "unknown",
    };
  });
}
