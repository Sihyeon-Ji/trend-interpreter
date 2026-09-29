/* 초안 1(/lab/o-report)의 서버 쪽 조립. lib/data.ts 의 함수만 부르고(읽기 전용), 화면에 필요한 칸만 골라 가볍게 넘긴다.
   판정(단계·쓸 때 조심·목록 나누기)은 백엔드 값 그대로이고, 여기서 새로 만드는 숫자는 검색 곡선에서 센 증감·순위뿐이다. */
import { getGenerationCurves, getKeywordBoard, getTermRecord, getTermSignals, getTermTopic, getUpdateFeed, getUpdatedAt, loadTermRecords } from "@/lib/data";
import { currentMeaning, headlineFor, textFor } from "@/lib/explain";
import type { Locale } from "@/lib/i18n";
import { riskOf } from "@/lib/keyword";
import { langTag, scriptLang } from "@/lib/lang";
import { L, sourceName, termLangLabel } from "@/lib/labels";
import { TARGET_REGIONS } from "@/lib/reader";
import { cleanSource } from "@/lib/sources";
import type { Evidence, KeywordBoard, KeywordCard, TermRecord } from "@/lib/types";
import type { GenerationCurve, Topic } from "@/lib/trends/types";
import {
  dailyIndex, dayIso, isStale, movingAverage, rankRows, readingOf, riskNoteOf, silhouette, weekly, windowGrowth,
  type Change, type DailyIndex, type Media, type Preview, type Row, type Silhouette, type SourceRef, type Weeks,
} from "./o-report";

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
  try { return new URL(url).hostname; } catch { return ""; }
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

/** 화면에 보여도 되는 근거인가, 그렇다면 어떤 종류로. 첫 화면 주소뿐인 근거(https://n.news.naver.com/ 같은 예시 자료)는
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

/* 앱의 sourceName 에 없는 기사 주소 이름 */
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

const escapeRe = (x: string) => x.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

function refOf(e: Evidence, name: string, locale: Locale): SourceRef | null {
  const kind = visibleKind(e);
  if (!kind) return null;
  const row = cleanSource(e, name, locale);
  const src = nameOf(e.source_domain, locale);
  // 수집기가 제목 앞에 붙인 출처 이름("네이버 뉴스 · …")을 뗀다 — 출처 칸에 이미 있다
  const prefixes = [src, sourceName("ko", e.source_domain), "네이버 뉴스", "Naver News"];
  const hit = prefixes.find((x) => new RegExp(`^${escapeRe(x)}\\s*[·|:–-]\\s*`).test(row.title));
  const title = hit ? row.title.replace(new RegExp(`^${escapeRe(hit)}\\s*[·|:–-]\\s*`), "") : row.title;
  return { name: src, title: title || row.title, url: e.url, date: e.observed_at, kind };
}

/** 유래 옆에 붙일 근거 — 위키 먼저, 그다음 가장 오래된 기사 */
function originRefs(r: TermRecord, locale: Locale, max = 2): SourceRef[] {
  const refs = [...r.evidences].sort((a, b) => a.observed_at.localeCompare(b.observed_at))
    .map((e) => refOf(e, r.term.canonical, locale)).filter((x): x is SourceRef => !!x);
  const wiki = refs.filter((x) => x.kind === "wiki");
  const news = refs.filter((x) => x.kind === "news");
  const out: SourceRef[] = [];
  for (const x of [...wiki, ...news]) if (out.length < max && !out.some((o) => o.name === x.name)) out.push(x);
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

function previewOf(r: TermRecord, locale: Locale): Preview {
  const tx = textFor(r, locale);
  const textLang = locale === "en" && !r.en ? "ko" : undefined;
  // 유래 칸에 도메인만 들어온 자료(“wikipedia.org”)는 유래가 아니다
  const origin = tx?.origin && tx.origin !== "unknown" && !/^[a-z0-9.-]+\.[a-z]{2,}$/i.test(tx.origin.trim()) ? tx.origin : null;
  return {
    id: r.term.term_id,
    aliases: (r.term.aliases ?? []).filter((a) => a && a !== r.term.canonical).slice(0, 4),
    definition: tx ? headlineFor(tx, locale) : null,
    origin,
    nuance: tx?.nuance && tx.nuance !== "unknown" ? tx.nuance : null,
    plain: tx?.plain || null,
    textLang,
    refs: originRefs(r, locale),
    verified: r.term.status === "verified",
    media: mediaOf(r),
  };
}

/* ───────── 리포트(첫 화면) ───────── */

interface Stat { idx: DailyIndex | null; growth: number | null; prevGrowth: number | null; stale: boolean }

function statOf(curves: GenerationCurve[] | undefined, weeks: Weeks, boardAt: string): Stat {
  const idx = curves ? dailyIndex(curves) : null;
  if (!idx) return { idx: null, growth: null, prevGrowth: null, stale: false };
  const stale = isStale(idx, boardAt);
  if (stale) return { idx, growth: null, prevGrowth: null, stale };
  const w = weeks * 7;
  // 순위 변화는 4주 창만 — 12주는 세 창(252일)이 곡선 길이(180일)보다 길다
  return { idx, growth: windowGrowth(idx, w), prevGrowth: weeks === 4 ? windowGrowth(idx, w, w) : null, stale };
}

function thumbOf(c: KeywordCard): Row["thumb"] {
  const e = c.evidences.find((x) => x.kind === "short" && youtubeId(x.url));
  if (!e) return null;
  const id = youtubeId(e.url)!;
  return { src: `https://i.ytimg.com/vi/${id}/mqdefault.jpg`, href: `https://www.youtube.com/watch?v=${id}`, title: e.title };
}

function rowOf(c: KeywordCard, s: Stat, weeks: Weeks, locale: Locale, searchable: boolean): Row {
  const gloss = locale === "en" ? c.gloss_en || c.gloss_ko : c.gloss_ko || c.gloss_en;
  const risk = riskOf(c);
  const show = searchable && !!s.idx && !s.stale;
  return {
    id: c.term_id,
    name: c.canonical,
    lang: langTag(c.lang),
    reading: null,
    gloss,
    glossLang: locale === "en" && !c.gloss_en ? "ko" : undefined,
    lifecycle: c.lifecycle,
    diffusion: c.diffusion ?? null,
    risk,
    riskNote: riskNoteOf(c.risk_reasons, locale)?.text ?? null,
    regions: c.regions,
    growth: show ? s.growth : null,
    rank: null,
    rankChange: null,
    spark: show && s.idx && s.growth != null ? weekly(s.idx).map((v) => Math.round(v * 10) / 10) : null,   // 셀 수 없는 밈은 선도 그리지 않는다
    sparkRecent: weeks,
    lastUsed: c.last_used ?? null,
    thumb: thumbOf(c),
  };
}

/** 사전 항목의 대표 영상(유튜브)도 표지 그림으로 쓴다 — 썸네일 주소만, 파일은 받지 않는다.
 *  사진(위키미디어)은 저작자 표시가 필요해 표지에 쓰지 않고, 표시를 함께 다는 미리보기·항목 화면에서만 보인다. */
const videoThumb = (m: Media | null | undefined): Row["thumb"] => (m?.kind === "video" ? { src: m.src, href: m.href, title: m.title } : null);

export interface SpotItem { row: Row; shape: Silhouette | null; preview: Preview | null }

export interface Report {
  generatedAt: string;
  regions: string[];              // 백엔드가 실제로 고른 지역 (전체면 목표 지역 10곳)
  asked: string[];                // 주소에 적힌 지역 ([] = 전체)
  counts: Record<string, number>;
  totals: KeywordBoard["totals"];
  known: number;                  // 고른 지역에서 확인된 밈 수 (쓰이는 + 식는 + 사용 자제 — 칩 건수와 같은 규칙)
  page: number;
  pageSize: number;
  searchable: boolean;            // 한국이 들어 있어 네이버 검색 곡선을 쓸 수 있나
  lists: { rising: Row[]; fading: Row[]; caution: Row[] };
  previews: Record<string, Preview>;
  spotlight: { mode: "growth" | "plain" | "flat"; items: SpotItem[] };
  changes: Change[];
  dataRange: { from: string; to: string } | null;
}

export async function loadReport(asked: string[], weeks: Weeks, page: number, locale: Locale): Promise<Report> {
  const first = await getKeywordBoard(asked, 1);   // 실패하면 던진다 → error.tsx
  const size = first.page_size || 30;
  // '뜨는 밈' 은 순위를 매기려고 끝까지 받는다(30개가 넘는 경우는 전체 지역 33개 정도)
  const risingPages = Math.min(4, Math.ceil(first.totals.rising / size));
  const extra = await Promise.all(Array.from({ length: Math.max(0, risingPages - 1) }, (_, i) => getKeywordBoard(asked, i + 2).catch(() => null)));
  const rising = [...first.rising, ...extra.flatMap((b) => b?.rising ?? [])];
  const last = Math.max(1, Math.ceil(Math.max(first.totals.fading, first.totals.caution) / size));
  const p = Math.min(Math.max(1, page), last);
  const other = p === 1 ? first : (extra[p - 2] ?? (await getKeywordBoard(asked, p)));
  const fading = other.fading, caution = other.caution;

  const regions = first.regions;
  const searchable = regions.includes("KR");
  const cards = new Map<string, KeywordCard>();
  for (const c of [...rising, ...fading, ...caution]) if (!cards.has(c.term_id)) cards.set(c.term_id, c);
  const ids = [...cards.keys()];

  const [curveList, recordList, feed] = await Promise.all([
    searchable ? Promise.all(ids.map((id) => getGenerationCurves(id).catch(() => []))) : Promise.resolve(ids.map(() => [] as GenerationCurve[])),
    Promise.all(ids.map((id) => getTermRecord(id).catch(() => null))),
    getUpdateFeed(168).catch(() => null),
  ]);
  const stats = new Map(ids.map((id, i) => [id, statOf(curveList[i], weeks, first.generated_at)]));
  const previews: Record<string, Preview> = {};
  recordList.forEach((r) => { if (r) previews[r.term.term_id] = previewOf(r, locale); });

  const toRow = (c: KeywordCard): Row => {
    const reading = readingOf(c.canonical, previews[c.term_id]?.aliases ?? [], locale);
    const row = rowOf(c, stats.get(c.term_id)!, weeks, locale, searchable);
    return { ...row, reading, readingLang: reading && locale === "ko" ? "ko" : undefined, thumb: row.thumb ?? videoThumb(previews[c.term_id]?.media) };
  };

  // 뜨는 밈: 늘어난 정도 순위, 셀 수 없는 밈은 뒤에 백엔드 순서(최근에 쓰인 순) 그대로
  const risingRows = rising.map((c) => ({ ...toRow(c), prevGrowth: searchable ? stats.get(c.term_id)!.prevGrowth : null }));
  const ranked = rankRows(risingRows).map(({ row, rank, rankChange }) => ({ ...row, rank, rankChange }));
  const orderedRising = [...ranked.filter((r) => r.rank != null).sort((a, b) => a.rank! - b.rank!), ...ranked.filter((r) => r.rank == null)]
    .map(({ prevGrowth, ...r }) => { void prevGrowth; return r as Row; });

  // 이번 주 주목: 늘어난 밈 세 개. 검색 자료가 없는 지역은 최근에 쓰인 순서의 세 개(늘었다고 말하지 않는다)
  const up = orderedRising.filter((r) => r.rank != null && (r.growth ?? 0) > 0).slice(0, 3);
  const mode: Report["spotlight"]["mode"] = up.length ? "growth" : searchable && orderedRising.some((r) => r.rank != null) ? "flat" : "plain";
  const spotRows = mode === "growth" ? up : mode === "plain" ? orderedRising.slice(0, 3) : [];
  const spotlight = {
    mode,
    items: spotRows.map((row) => {
      const s = stats.get(row.id)!;
      return { row, shape: mode === "growth" && s.idx ? silhouette(s.idx, weeks * 7, weeks === 4 ? 2 : 3) : null, preview: previews[row.id] ?? null };
    }),
  };

  const ends = [...stats.values()].filter((s) => s.idx && !s.stale && s.growth != null).map((s) => s.idx!.end);
  const dataRange = searchable && ends.length ? { from: dayIso(Math.min(...ends)), to: dayIso(Math.max(...ends)) } : null;

  return {
    generatedAt: first.generated_at,
    regions,
    asked,
    counts: first.counts,
    totals: first.totals,
    known: asked.length === 1 ? first.counts[asked[0]] ?? 0 : asked.length === 0 ? first.counts.ALL ?? 0
      : first.totals.rising + first.totals.fading + first.caution.filter((c) => c.risk_level === "avoid").length,
    page: p,
    pageSize: size,
    searchable,
    lists: { rising: orderedRising, fading: fading.map(toRow), caution: caution.map(toRow) },
    previews,
    spotlight,
    changes: changesFor(feed?.items ?? [], regions, locale),
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
      out.push({ kind: "spike", at: i.at, id: null, label: i.label, lang: scriptLang(i.label, i.region), region: i.region, note });
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

/* ───────── 밈 항목 ───────── */

export interface GenLine { gen: string; label: string; weeklyValues: number[]; peak: string | null; growth: number | null }

export interface EntryTrend {
  start: string;
  end: string;
  daily: number[];               // 7일 평균
  growth4: number | null;
  growth12: number | null;
  stale: boolean;
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
  riskNote: string | null;       // 쓸 때 조심 이유 한 줄 — 커뮤니티 인용을 뗀 쉬운 말
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

const GEN_ORDER = ["10s", "20s", "30s", "40s", "50s+"];

function trendOf(curves: GenerationCurve[], boardAt: string | null, locale: Locale): EntryTrend | null {
  const idx = dailyIndex(curves);
  if (!idx || idx.values.length < 14) return null;
  const stale = !!boardAt && isStale(idx, boardAt);
  const labels = L(locale).generation;
  const gens = curves.filter((c) => c.points.length > 0).sort((a, b) => GEN_ORDER.indexOf(a.generation) - GEN_ORDER.indexOf(b.generation)).map((c) => {
    const one = dailyIndex([c])!;
    // 모든 연령대가 같은 가로축을 쓰게 전체 기간으로 늘린다
    const padded: DailyIndex = { start: idx.start, end: idx.end, values: Array.from({ length: idx.values.length }, (_, i) => one.values[i + idx.start - one.start] ?? 0) };
    return {
      gen: c.generation,
      label: labels[c.generation as keyof typeof labels] ?? c.generation,
      weeklyValues: weekly(padded).map((v) => Math.round(v * 10) / 10),
      peak: c.peak_date,
      growth: stale ? null : windowGrowth(padded, 28),
    };
  });
  return {
    start: dayIso(idx.start),
    end: dayIso(idx.end),
    daily: movingAverage(idx.values).map((v) => Math.round(v * 10) / 10),
    growth4: stale ? null : windowGrowth(idx, 28),
    growth12: stale ? null : windowGrowth(idx, 84),
    stale,
    gens,
  };
}

function variantsOf(topic: Topic | null, locale: Locale): Variant[] {
  if (!topic) return [];
  const labels = L(locale).region;
  return topic.variants
    .filter((v) => v.region && labels[v.region])
    .map((v) => {
      const raw = (locale === "en" ? v.what_changed.en || v.what_changed.ko : v.what_changed.ko || v.what_changed.en) ?? "";
      const diff = raw && !raw.startsWith("근거 부족") ? raw : null;
      return {
        region: v.region,
        regionLabel: labels[v.region],
        local: v.local_name,
        localLang: scriptLang(v.local_name, v.region),
        diff,
        diffLang: locale === "en" && !v.what_changed.en && diff ? "ko" : undefined,
        memes: v.local_memes.filter((m) => m.label && m.label !== v.local_name).slice(0, 4).map((m) => ({ label: m.label, lang: scriptLang(m.label, v.region) })),
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
  const sources = [...record.evidences].sort((a, b) => b.observed_at.localeCompare(a.observed_at))
    .map((e) => refOf(e, term.canonical, locale)).filter((x): x is SourceRef => !!x);
  const seen = new Set<string>();
  const uniqueSources = sources.filter((s) => { const k = `${s.name}|${s.title}`; if (seen.has(k)) return false; seen.add(k); return true; });
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
    riskNote: riskNoteOf(term.risk_reasons ?? [], locale)?.text ?? null,
    regions: signals?.regions?.length ? signals.regions : cur?.regions ?? [],
    lastUsed: signals?.last_used ?? null,
    canMake: verified && term.risk_level !== "avoid",
    firstAdded: history.at(-1)?.from ?? null,
    sources: uniqueSources.slice(0, 12),
    communityCount: record.evidences.filter(isCommunity).length,
    trend: trendOf(curves, updatedAt, locale),
    variants: variantsOf(topic, locale),
    history,
    updatedAt,
  };
}

/* ───────── 찾기 색인 (프레임의 검색 칸이 처음 쓸 때 받는다) ───────── */

export interface IndexItem { id: string; name: string; lang?: string; aliases: string[]; gloss: string; glossLang?: string; risk: ReturnType<typeof riskOf> }

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
    };
  });
}
