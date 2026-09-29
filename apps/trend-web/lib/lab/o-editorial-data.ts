/* 시안 '에디토리얼형' 의 서버 데이터. 공용 로더(lib/data.ts)를 읽기만 하고, 한 판(edition)에 필요한 것을 한 번에 모은다.
   api 모드에서 대시보드가 실패하면 예시로 바꾸지 않고 null 을 돌려 화면이 '불러오지 못했습니다' 를 낸다(공용 규칙과 같다). */
import { getGenerationCurves, getKeywordBoard, getMeta, getTermRecord, getUpdateFeed, isSampleMode, loadTermRecords } from "@/lib/data";
import { termRegions, lastUsedOf } from "@/lib/dictionary/regions";
import { langTag, scriptLang } from "@/lib/lang";
import { sampleCardsById } from "@/lib/sample/keyword-board";
import type { GenerationCurve } from "@/lib/trends/types";
import type { KeywordBoard, KeywordCard, TermRecord } from "@/lib/types";
import { EDITION_ORDER, editionRegions, searchSummary, type EditionKey, type SearchSummary, type SinceItem } from "./o-editorial";

const API = process.env.TREND_API_URL ?? "http://localhost:8080";
const TARGETS: string[] = [...EDITION_ORDER];

export interface Issue {
  edition: EditionKey;
  board: KeywordBoard;                                   // 1쪽 (목록마다 30개)
  cover: KeywordCard | null;
  coverFallback: boolean;                                // 지금 쓰이는 밈이 없어 식어 가는 밈에서 커버를 골랐다
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

  // '요즘 더 찾는 밈' 은 모든 쪽에서 고른다 — 1쪽(30개)만 보면 식어 가는 밈 뒤쪽의 검색 급증이 빠진다
  const lastPage = Math.max(1, ...(["rising", "fading", "caution"] as const).map((k) => Math.ceil((board.totals[k] ?? 0) / (board.page_size || 30))));
  const rest = lastPage > 1
    ? await Promise.all(Array.from({ length: lastPage - 1 }, (_, i) => getKeywordBoard(regions, i + 2).catch(() => null)))
    : [];
  const pages = [board, ...rest.filter((b): b is KeywordBoard => !!b)];
  const usable = uniq(pages.flatMap((b) => [...b.rising, ...b.fading]));      // 사용 자제는 주의 목록에만 있다

  const cover = board.rising[0] ?? board.fading[0] ?? null;
  const withCurves = uniq([...usable, ...(cover ? [cover] : [])]).filter((c) => (c.gen_peaks?.length ?? 0) > 0);

  const [curves, coverRecord, feed, meta] = await Promise.all([
    Promise.all(withCurves.map((c) => getGenerationCurves(c.term_id).catch((): GenerationCurve[] => []).then((cv) => [c.term_id, cv] as [string, GenerationCurve[]]))),
    cover ? getTermRecord(cover.term_id).catch(() => null) : Promise.resolve(null),
    getUpdateFeed(168).catch(() => null),
    getMeta().catch(() => null),
  ]);

  const searches: Record<string, SearchSummary> = {};
  for (const [id, cv] of curves) {
    const s = searchSummary(cv);
    if (s) searches[id] = s;
  }
  const searched = usable.filter((c) => !!searches[c.term_id]);

  const inEdition = (cardRegions: string[] | undefined) => {
    const rs = cardRegions ?? [];
    if (edition === "ALL") return rs.some((r) => TARGETS.includes(r));
    return rs.includes(edition);
  };
  const since: SinceItem[] = [];
  for (const it of feed?.items ?? []) {
    if (it.kind === "spike") {
      if (!it.region || edition === "GLOBAL") continue;
      if (edition === "ALL" ? !TARGETS.includes(it.region) : it.region !== edition) continue;
      since.push({ kind: "spike", at: it.at, label: it.label, lang: scriptLang(it.label, it.region), reason: it.reason ?? null });
    } else if ((it.kind === "verified" || it.kind === "meaning_changed") && it.term_id && it.card && inEdition(it.card.regions)) {
      const risk = it.card.risk_level === "caution" || it.card.risk_level === "avoid" ? it.card.risk_level : null;
      since.push({ kind: it.kind, at: it.at, label: it.card.canonical, termId: it.term_id, lang: langTag(it.card.lang), risk });
    }
  }
  since.sort((a, b) => b.at.localeCompare(a.at));

  return {
    edition, board, cover, coverFallback: !board.rising.length && !!cover, coverRecord,
    searches, searched, since,
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
