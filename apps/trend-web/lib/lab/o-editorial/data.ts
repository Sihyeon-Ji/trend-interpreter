/* 시안 '에디토리얼형' 의 서버 데이터. 공용 로더(lib/data.ts)를 읽기만 하고, 한 판(edition)에 필요한 것을 한 번에 모은다.
   api 모드에서 대시보드가 실패하면 예시로 바꾸지 않고 null 을 돌려 화면이 '불러오지 못했습니다' 를 낸다(공용 규칙과 같다). */
import { getGenerationCurves, getKeywordBoard, getMeta, getTermRecord, getUpdateFeed, isSampleMode, loadTermRecords } from "@/lib/data";
import { termRegions, lastUsedOf } from "@/lib/dictionary/regions";
import type { Locale } from "@/lib/i18n";
import { langTag, scriptLang } from "@/lib/lang";
import { sampleCardsById } from "@/lib/sample/keyword-board";
import type { GenerationCurve } from "@/lib/trends/types";
import type { KeywordBoard, KeywordCard, TermRecord } from "@/lib/types";
import {
  EDITION_ORDER, editionMembers, editionRegions, glossOf, pickCover, riskKind, searchSummary, tidyGloss,
  type CoverPick, type EditionKey, type RiskKind, type SearchSummary, type SinceItem,
} from "./index";

const API = process.env.TREND_API_URL ?? "http://localhost:8080";
const TARGETS: string[] = [...EDITION_ORDER];

export interface Issue {
  edition: EditionKey;
  board: KeywordBoard;                                   // 1쪽 (목록마다 30개)
  cover: CoverPick | null;                               // 커버와 고른 규칙(lib/lab/o-editorial.ts pickCover)
  coverRecord: TermRecord | null;
  searches: Record<string, SearchSummary>;               // 네이버 곡선이 있는 밈만 (term_id → 4주 변화)
  searched: KeywordCard[];                               // '요즘 더 찾는 밈' 후보 (모든 쪽에서, 사용 자제 제외)
  since: SinceItem[];                                    // 최근 7일 변화 (이 판의 것만, 최신 먼저)
  updatedAt: string | null;
}

const uniq = (cards: KeywordCard[]) => [...new Map(cards.map((c) => [c.term_id, c])).values()];

/** 한 판의 이번 주 호. 대시보드가 실패하면 null. */
export async function getIssue(edition: EditionKey): Promise<Issue | null> {
  const regions = editionRegions(edition);
  let board: KeywordBoard;
  try {
    board = await getKeywordBoard(regions, 1);
  } catch {
    return null;
  }

  // '요즘 더 찾는 밈' 과 커버는 모든 쪽에서 고른다 — 1쪽(30개)만 보면 식어 가는 밈 뒤쪽의 검색 급증이 빠진다
  const lastPage = Math.max(1, ...(["rising", "fading", "caution"] as const).map((k) => Math.ceil((board.totals[k] ?? 0) / (board.page_size || 30))));
  const rest = lastPage > 1
    ? await Promise.all(Array.from({ length: lastPage - 1 }, (_, i) => getKeywordBoard(regions, i + 2).catch(() => null)))
    : [];
  const pages = [board, ...rest.filter((b): b is KeywordBoard => !!b)];
  const rising = uniq(pages.flatMap((b) => b.rising));
  const fading = uniq(pages.flatMap((b) => b.fading));
  const usable = uniq([...rising, ...fading]);                                // 사용 자제는 주의 목록에만 있다
  const withCurves = usable.filter((c) => (c.gen_peaks?.length ?? 0) > 0);

  const [curves, feed, meta] = await Promise.all([
    Promise.all(withCurves.map((c) => getGenerationCurves(c.term_id).catch((): GenerationCurve[] => []).then((cv) => [c.term_id, cv] as [string, GenerationCurve[]]))),
    getUpdateFeed(168).catch(() => null),
    getMeta().catch(() => null),
  ]);

  const searches: Record<string, SearchSummary> = {};
  for (const [id, cv] of curves) {
    const s = searchSummary(cv);
    if (s) searches[id] = s;
  }
  const searched = usable.filter((c) => !!searches[c.term_id]);
  const cover = pickCover(rising, fading, searches, board.generated_at);
  const coverRecord = cover ? await getTermRecord(cover.card.term_id).catch(() => null) : null;

  const members = new Set(editionMembers(edition));
  const inEdition = (cardRegions: string[] | undefined) => {
    const rs = cardRegions ?? [];
    if (edition === "GLOBAL") return rs.includes("GLOBAL");
    return rs.some((r) => members.has(r));
  };
  const since: SinceItem[] = [];
  for (const it of feed?.items ?? []) {
    if (it.kind === "spike") {
      if (!it.region || edition === "GLOBAL" || !TARGETS.includes(it.region) || !members.has(it.region)) continue;
      since.push({ kind: "spike", at: it.at, label: it.label, lang: scriptLang(it.label, it.region), reason: it.reason ?? null });
    } else if ((it.kind === "verified" || it.kind === "meaning_changed") && it.term_id && it.card && inEdition(it.card.regions)) {
      const risk = it.card.risk_level === "caution" || it.card.risk_level === "avoid" ? it.card.risk_level : null;
      since.push({ kind: it.kind, at: it.at, label: it.card.canonical, termId: it.term_id, lang: langTag(it.card.lang), risk });
    }
  }
  since.sort((a, b) => b.at.localeCompare(a.at));

  return {
    edition, board, cover, coverRecord, searches, searched, since,
    updatedAt: meta?.last_run ?? board.generated_at ?? null,
  };
}

/** 한 목록의 한 쪽 (꼭지 전체 보기). 실패하면 null. */
export async function getListPage(edition: EditionKey, page: number): Promise<KeywordBoard | null> {
  try {
    return await getKeywordBoard(editionRegions(edition), page);
  } catch {
    return null;
  }
}

/** 한 목록의 한 쪽에 실린 밈의 검색 변화(포스터의 '검색' 숫자) — 곡선이 있는 밈만. 곡선은 5분 캐시(lib/data). */
export async function getSearches(cards: KeywordCard[]): Promise<Record<string, SearchSummary>> {
  const out: Record<string, SearchSummary> = {};
  const withCurves = cards.filter((c) => (c.gen_peaks?.length ?? 0) > 0);
  const got = await Promise.all(withCurves.map((c) => getGenerationCurves(c.term_id).catch((): GenerationCurve[] => []).then((cv) => [c.term_id, cv] as const)));
  for (const [id, cv] of got) {
    const s = searchSummary(cv);
    if (s) out[id] = s;
  }
  return out;
}

const ID = /^[\w.:-]{1,64}$/;

/** 스크랩한 밈의 지금 상태 — 대시보드 카드를 id 로. 실패하면 null(화면이 알린다). */
export async function getCardsByIds(ids: string[]): Promise<KeywordCard[] | null> {
  const clean = [...new Set(ids.filter((id) => ID.test(id)))].slice(0, 50);
  if (!clean.length) return [];
  if (isSampleMode) return sampleCardsById(clean);
  try {
    const res = await fetch(`${API}/dashboard/cards?ids=${clean.map(encodeURIComponent).join(",")}`, { cache: "no-store", signal: AbortSignal.timeout(10_000) });
    if (!res.ok) return null;
    return (await res.json()) as KeywordCard[];
  } catch {
    return null;
  }
}

export interface Found { record: TermRecord; regions: string[]; lastUsed: string | null; score: number }

const norm = (s: string) => s.toLowerCase().normalize("NFKC").replace(/[\s·・\-_'’"“”.,!?~]+/g, "");

/** 찾기 — 확인을 거친 사전에서 이름·다른 표기·뜻으로. 이름이 맞을수록 앞. 사전을 못 받으면 null. */
export async function searchDictionary(q: string): Promise<Found[] | null> {
  const { records, ok } = await loadTermRecords();
  if (!ok) return null;
  const key = norm(q);
  if (!key) return [];
  const out: Found[] = [];
  for (const r of records) {
    const names = [r.term.canonical, ...(r.term.aliases ?? [])].map(norm);
    const meaning = [r.ko?.definition, r.en?.definition, ...r.meanings.filter((m) => !m.valid_to).map((m) => m.definition)].filter(Boolean).join(" ");
    let score = 0;
    if (names.some((n) => n === key)) score = 100;
    else if (names.some((n) => n.startsWith(key))) score = 80;
    else if (names.some((n) => n.includes(key))) score = 60;
    else if (norm(meaning).includes(key)) score = 30;
    if (score) out.push({ record: r, regions: termRegions(r), lastUsed: lastUsedOf(r), score });
  }
  return out.sort((a, b) => b.score - a.score || a.record.term.canonical.localeCompare(b.record.term.canonical)).slice(0, 40);
}

/** 머리 찾기 칸의 바로 보기 — 확인을 거친 사전의 가벼운 색인(이름·다른 표기·뜻 한 줄·쓸 때 조심·단계). 근거는 싣지 않는다. */
export interface IndexEntry { id: string; name: string; lang?: string; aliases: string[]; gloss: string; glossLang?: string; risk: RiskKind; lifecycle: string; diffusion: string | null }

export async function dictionaryIndex(locale: Locale): Promise<IndexEntry[] | null> {
  const { records, ok } = await loadTermRecords();
  if (!ok) return null;
  return records.filter((r) => r.term.status === "verified").map((r) => {
    const t = r.term;
    const tx = locale === "en" ? r.en ?? null : r.ko ?? null;
    const fallback = r.meanings.find((m) => !m.valid_to)?.definition ?? "";
    const g = tx?.definition ? { text: tx.definition, lang: undefined } : glossOf(locale, { gloss_ko: r.ko?.definition ?? fallback, gloss_en: r.en?.definition ?? "" });
    return {
      id: t.term_id, name: t.canonical, lang: langTag(t.lang), aliases: (t.aliases ?? []).slice(0, 6),
      gloss: tidyGloss(g.text).slice(0, 140), glossLang: g.lang, risk: riskKind(t), lifecycle: t.lifecycle ?? "unknown", diffusion: t.diffusion ?? null,
    };
  });
}
