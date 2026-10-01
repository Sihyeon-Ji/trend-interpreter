/* 데이터 접근 계층. 지금은 예시 데이터, DATA_MODE=api 면 Python(ADK) 서비스에서 가져온다.
   화면은 이 함수들만 부른다 — 소스가 바뀌어도 화면은 안 바뀌게. */
import { SAMPLE_BOARD } from "./sample/trend-board";
import type { GenerationCurve, Meta, Topic, TrendBoard, TrendWhy, UpdateFeed, UpdateItem } from "./trends/types";
import { SAMPLE_GRAPH, SAMPLE_GRAPH_CONTENTS } from "./sample/graph";
import type { GraphContent, GraphContentSummary, KeywordBoard, KeywordCard, PipelineStage, ReviewItem, TermRecord } from "./types";
import type { Locale } from "./i18n";
import type { Reader } from "./reader";
import { SAMPLE_COPY, SAMPLE_COPY_EN, SAMPLE_QUEUE, SAMPLE_RECORDS, SAMPLE_REWRITES, SAMPLE_STAGES } from "./sample/dictionary";
import { explainMessage, type ExplainResult } from "./explain";
import { sampleCardsById, sampleKeywordBoard, sampleSignals } from "./sample/keyword-board";
import { SAMPLE_WHY, sampleUpdateFeed } from "./sample/updates";
import { TARGET_REGIONS } from "./reader";

export const isSampleMode = process.env.DATA_MODE !== "api";
const API = process.env.TREND_API_URL ?? "http://localhost:8080";

/* 예시 모드도 백엔드 views.shown_evidences 와 같이 — 커뮤니티 글은 쓰임 지표(예시 대시보드의 '마지막 쓰임')로만 두고
   사전 항목·검수·해석 화면의 근거로 보이지 않는다(ADR 0003). */
const SHOWN_RECORDS: TermRecord[] = SAMPLE_RECORDS.map((r) => ({ ...r, evidences: r.evidences.filter((e) => e.kind !== "community") }));

class ApiError extends Error {
  constructor(path: string, readonly status: number) {
    super(`${path} → ${status}`);
  }
}

async function api<T>(path: string, revalidate = 60): Promise<T> {
  const res = await fetch(`${API}${path}`, { next: { revalidate } });
  if (!res.ok) throw new ApiError(path, res.status);
  return res.json() as Promise<T>;
}

/** api 모드에서 서버가 죽어 있으면 예시 데이터로 내려간다 — 데모 중 빈 화면을 막는다. */
async function apiOr<T>(path: string, fallback: T, revalidate = 60): Promise<T> {
  try {
    return await api<T>(path, revalidate);
  } catch {
    return fallback;
  }
}

/** 2MB 가 넘어 Next 데이터 캐시에 넣지 못하는 응답(사전 전체 /terms 2.7MB)은 서버 메모리에 잠깐 둔다 — 사전 화면을 열 때마다
 *  API 에서 통째로 다시 받았다(2026-09-29 운영 로그 'items over 2MB can not be cached'). */
const bigCache = new Map<string, { at: number; value: unknown }>();
async function apiBig<T>(path: string, ttlMs = 60_000): Promise<T> {
  const hit = bigCache.get(path);
  if (hit && Date.now() - hit.at < ttlMs) return hit.value as T;
  const res = await fetch(`${API}${path}`, { cache: "no-store" });
  if (!res.ok) throw new ApiError(path, res.status);
  const value = (await res.json()) as T;
  bigCache.set(path, { at: Date.now(), value });
  return value;
}

/** 사전 색인용. 서버가 실패하면 예시 데이터로 바꿔 넣지 않고 실패를 알린다 — 운영 사용자가 예시 52개를 실제 사전으로
 *  보게 되던 것(2026-09-29 검토). 예시 모드도 공개 사전처럼 확인된 표현만 싣는다. */
export async function loadTermRecords(): Promise<{ records: TermRecord[]; ok: boolean }> {
  if (isSampleMode) return { records: SHOWN_RECORDS.filter((r) => r.term.status === "verified"), ok: true };
  try {
    return { records: await apiBig<TermRecord[]>("/terms"), ok: true };
  } catch {
    return { records: [], ok: false };
  }
}

/** 사전 항목 하나. 서버가 "없다/제외됐다"(404)고 하면 null → 없는 말 화면.
 *  api 모드에서 서버가 답하지 않으면 예시 데이터로 바꾸지 않고 던진다 → app/dictionary/[termId]/error.tsx 가 '다시 불러오기' 를 낸다
 *  (예시 수치가 실제처럼 보이던 것, 개편 검토 2차). */
export async function getTermRecord(termId: string): Promise<TermRecord | null> {
  if (isSampleMode) return SHOWN_RECORDS.find((r) => r.term.term_id === termId) ?? null;
  try {
    return await api<TermRecord | null>(`/terms/${encodeURIComponent(termId)}`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

/** 사전 항목이 속한 주제(나라별 차이·관련 표현). 보드를 못 받으면 그 절을 내지 않는다 — 예시 주제로 바꾸지 않는다. */
export async function getTermTopic(termId: string, canonical: string): Promise<Topic | null> {
  const find = (b: TrendBoard) => b.topics.find((x) => x.variants.some((v) => v.term_id === termId) || x.name.ko === canonical || x.name.en === canonical) ?? null;
  if (isSampleMode) return find(SAMPLE_BOARD);
  try {
    return find(await api<TrendBoard>("/trends/board", 30));
  } catch {
    return null;
  }
}

/** 사전 항목 머리의 '갱신' 시각 — 마지막 정상 갱신(ADR 0001). 예시 모드는 예시 대시보드와 같은 값. */
export async function getUpdatedAt(): Promise<string | null> {
  if (isSampleMode) return sampleKeywordBoard([]).generated_at;
  return (await getMeta())?.last_run ?? null;
}

/** 관리 화면 조회 — 예시 데이터로 바꾸지 않고(예시 문구를 보고 실제 뜻을 승인하게 된다), 캐시하지 않는다(결정 뒤 건수가 그대로였다).
 *  실패하면 던진다 → app/admin/error.tsx 가 '다시 불러오기' 를 보인다. */
async function apiNoStore<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`, { cache: "no-store" });
  if (!res.ok) throw new ApiError(path, res.status);
  return res.json() as Promise<T>;
}

export async function getPipelineStages(): Promise<PipelineStage[]> {
  return isSampleMode ? SAMPLE_STAGES : apiNoStore<PipelineStage[]>("/pipeline/stages");
}

/** 예시 모드는 예시 사전에서 지금 실린 뜻·근거를 붙인다(백엔드 views.review_items 와 같은 규칙).
 *  새 말은 제안보다 앞 판 가운데 확인된 마지막 것을, 문서 대조의 제안(고칠 안·위키끼리 다름·사전에서 뺄지)은 공개 중인 지금 뜻을 current 로. */
function sampleQueue(): ReviewItem[] {
  return SAMPLE_QUEUE.map((q) => {
    const rec = SHOWN_RECORDS.find((r) => r.term.term_id === q.term_id);
    const cur = q.kind === "new"
      ? (rec?.meanings.filter((m) => m.version < (q.proposed?.version ?? 0) && (m.verification === "verified_auto" || m.verification === "verified_human")) ?? []).at(-1)
      : rec?.meanings.find((m) => m.valid_to == null);
    return { ...q, lang: rec?.term.lang ?? null, current: cur ?? null, meaning_id: q.kind === "new" ? q.proposed?.meaning_id ?? null : cur?.meaning_id ?? null,
      token: q.token ?? `sample-${q.term_id}`,
      evidences: (rec?.evidences ?? []).filter((e) => e.kind !== "datalab").slice(0, 5), weekly: rec?.weekly ?? [] };
  });
}

export async function getReviewQueue(): Promise<ReviewItem[]> {
  return isSampleMode ? sampleQueue() : apiNoStore<ReviewItem[]>("/review/queue");
}

/** 관리 '리스크' 탭 — 사전에 오른 말 전부. 예시로 내려가지 않고 캐시하지 않는다(결정 뒤 바로 보여야 한다). */
export async function getRiskRecords(): Promise<TermRecord[]> {
  return isSampleMode ? SHOWN_RECORDS : apiNoStore<TermRecord[]>("/terms");
}

export function getSampleCopy(locale: Locale): string {
  return locale === "en" ? SAMPLE_COPY_EN : SAMPLE_COPY;
}

/** 메시지 해석. api 모드에서는 Python 서비스가 사전 매칭 + 로컬 Gemma 재작성('쉽게 풀어 쓰면')을 돌려준다.
 *  샘플 모드에서는 로컬 매칭 + 예시 메시지에 대해 미리 생성해 둔 재작성만 쓴다(규칙 치환 없음). */
export async function explain(text: string, locale: Locale, reader: Reader = {}): Promise<ExplainResult> {
  if (!isSampleMode) {
    // 서버는 매칭된 용어 id 와 '쉽게 풀어 쓰면'(모델 재작성)만 돌려주고, 문장 조립은 화면 언어 규칙(lib/explain.ts)이 맡는다
    const res = await fetch(`${API}/explain`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ text, lang: locale, reader: { gen: reader.gen, region: reader.region } }) });
    if (!res.ok) throw new Error(`/explain → ${res.status}`);
    const { term_ids, plain } = (await res.json()) as { term_ids: string[]; plain: string | null };
    // 서버 매칭은 확인 중(needs_review)인 용어도 돌려준다 — 공개 목록(/terms 는 verified 만)이 아니라 id 마다 받는다(/terms/{id} 는 확인 중도 준다).
    // 해석 한 번마다 사전 전체(/terms?status=all 8MB + /terms 2.7MB)를 받던 것을 찾은 표현만 받게 했다. 못 받은 표현은 뺀다.
    const got = await Promise.all(term_ids.slice(0, 20).map((id) => api<TermRecord | null>(`/terms/${encodeURIComponent(id)}`, 300).catch(() => null)));
    const picked = got.filter((r): r is TermRecord => !!r);
    return explainMessage(text, picked, locale, plain, reader);
  }
  const plain = SAMPLE_REWRITES[locale][text.trim()] ?? null;
  return explainMessage(text, SHOWN_RECORDS, locale, plain, reader);
}

export async function getMeta(): Promise<Meta | null> {
  return isSampleMode ? null : apiOr<Meta | null>("/meta", null, 30);
}

/** 실패를 null 로 알린다 — 예시 데이터로 바꿔 치지 않는다(실데이터 화면에 예시가 섞이면 알아챌 수 없다, 화면 개편 2차 검토). */
async function apiOrNull<T>(path: string, revalidate: number | false = 60): Promise<T | null> {
  try {
    const res = await fetch(`${API}${path}`, revalidate === false ? { cache: "no-store" } : { next: { revalidate } });
    return res.ok ? ((await res.json()) as T) : null;
  } catch {
    return null;
  }
}

/** 최근 변화 목록(이용자 종류만) — 지도 화면의 '최근 변화 n건' 링크가 쓴다. 서버가 없으면 빈 목록. */
export async function getUpdates(hours = 48): Promise<UpdateItem[]> {
  if (isSampleMode) return sampleUpdateFeed().items;
  return (await apiOrNull<UpdateFeed>(`/updates?hours=${hours}`, 30))?.items ?? [];
}

/** 최근 변화 한 줄 + 대시보드 카드(뜻·단계·리스크·지역). 대시보드에 없는 표현은 card 가 없다 → 칸은 '—'. */
export type UpdateRow = UpdateItem & { card?: KeywordCard };
export interface UpdatePage { items: UpdateRow[]; counts: Record<string, number>; total: number; updated_at: string | null }

const cardIndex = (cards: KeywordCard[] | null) => new Map((cards ?? []).map((c) => [c.term_id, c]));
const feedIds = (items: UpdateItem[]) => [...new Set(items.map((i) => i.term_id).filter((id): id is string => !!id))];

/** '최근 변화' 화면. 서버가 목록을 못 주면 null(화면이 '불러오지 못했습니다'). 대시보드 카드는 붙이기만 하므로 없어도 목록은 보인다.
 *  카드는 행에 나온 표현 id 로 한 번에 받는다 — 대시보드 첫 쪽(30개)에서 찾으면 그 밖의 밈이 빈칸이 됐다(개편 통합 09-29). */
export async function getUpdateFeed(hours = 48): Promise<UpdatePage | null> {
  if (isSampleMode) {
    const feed = sampleUpdateFeed();
    const cards = cardIndex(sampleCardsById(feedIds(feed.items)));
    return { ...feed, items: feed.items.map((i) => ({ ...i, card: i.term_id ? cards.get(i.term_id) : undefined })), updated_at: SAMPLE_BOARD.generated_at };
  }
  const [feed, meta] = await Promise.all([apiOrNull<UpdateFeed>(`/updates?hours=${hours}&limit=300`, 30), getMeta()]);
  if (!feed || !Array.isArray(feed.items)) return null;   // 예전 백엔드(목록만 주던 /updates)도 '불러오지 못했습니다' 로
  const ids = feedIds(feed.items).slice(0, 200);
  // getKeywordBoard 와 같은 이유로 Next 데이터 캐시에 넣지 않는다
  const cards = cardIndex(ids.length ? await apiOrNull<KeywordCard[]>(`/dashboard/cards?ids=${ids.map(encodeURIComponent).join(",")}`, false) : []);
  return { ...feed, items: feed.items.map((i) => ({ ...i, card: i.term_id ? cards.get(i.term_id) : undefined })), updated_at: meta?.last_run ?? null };
}

/** 백엔드 pipeline/views.py CountryPage 와 1:1 */
export interface CountryPage { region: string; items: TrendBoard["items"]; why: TrendWhy[]; terms: TermRecord[]; generation_share: Record<string, number>; updated_at: string | null }

/** 나라 화면. 밈 목록은 대시보드와 같은 카드(board — 목표 지역만), 이유는 최근 7일에서 원인을 찾은 것만(뺀 건수는 why_hidden). */
export interface CountryView { region: string; items: TrendBoard["items"]; why: TrendWhy[]; why_hidden: number; board: KeywordBoard | null; updated_at: string | null }

const WHY_DAYS = 7;

function recentWhy(all: TrendWhy[], region: string, ref: string | null) {
  const end = ref ? Date.parse(ref) : NaN;
  const from = Number.isNaN(end) ? null : new Date(end - WHY_DAYS * 86_400_000).toISOString().slice(0, 10);
  const recent = all.filter((w) => w.region === region && (!from || String(w.date).slice(0, 10) >= from));
  const shown = recent.filter((w) => w.trigger !== "unknown").sort((a, b) => String(b.date).localeCompare(String(a.date)));
  return { why: shown, why_hidden: recent.length - shown.length };
}

/** 실패하면 null — 빈 페이지·1970년 갱신 시각으로 '자료 없음' 처럼 보이게 하지 않는다. */
export async function getCountryPage(region: string): Promise<CountryView | null> {
  const target = TARGET_REGIONS.includes(region);
  if (isSampleMode) {
    const items = SAMPLE_BOARD.items.filter((i) => i.region === region);
    return { region, items, ...recentWhy(SAMPLE_WHY, region, SAMPLE_BOARD.generated_at), board: target ? sampleKeywordBoard([region]) : null, updated_at: SAMPLE_BOARD.generated_at };
  }
  const [page, board] = await Promise.all([
    apiOrNull<CountryPage>(`/countries/${encodeURIComponent(region)}`, 30),
    target ? apiOrNull<KeywordBoard>(`/dashboard?regions=${encodeURIComponent(region)}`, false) : Promise.resolve(null),
  ]);
  if (!page || (target && !board)) return null;
  return { region, items: page.items, ...recentWhy(page.why ?? [], region, page.updated_at), board, updated_at: page.updated_at };
}

export async function getGenerationCurves(termId: string): Promise<GenerationCurve[]> {
  return isSampleMode ? [] : apiOr<GenerationCurve[]>(`/terms/${encodeURIComponent(termId)}/generations`, [], 300);
}

/** views.ReviewStats — needs_review 는 새 말(조사 결과) 검수 대기, proposals 는 문서 대조의 제안(이미 실린 말이라 비율에 넣지 않는다) */
export interface ReviewStats { verified_auto: number; verified_human: number; needs_review: number; rejected: number; proposals?: number }

/** 자동 확인 vs 사람 검수 비율 — 관리자 화면의 '자동화 정도' 표시. */
export async function getReviewStats(): Promise<ReviewStats> {
  if (isSampleMode) {
    const cur = SAMPLE_RECORDS.map((r) => r.meanings.find((m) => !m.valid_to) ?? r.meanings.at(-1)).filter(Boolean);
    const count = (v: string) => cur.filter((m) => m!.verification === v).length;
    const fresh = SAMPLE_QUEUE.filter((q) => q.kind === "new").length;
    return { verified_auto: count("verified_auto"), verified_human: count("verified_human"), needs_review: fresh, rejected: count("rejected"),
      proposals: SAMPLE_QUEUE.length - fresh };
  }
  return apiNoStore<ReviewStats>("/review/stats");
}

/** 키워드 대시보드 (Plan 04). regions 가 비면 목표 지역 전체, page 는 목록마다 몇째 쪽(30개씩). 지역 판정과 목록 나누기는 백엔드 규칙이 한다.
 *  api 모드에서 서버가 실패하면 예외를 던진다 — 예시 데이터를 실제처럼 보여 주지 않고 화면이 '불러오지 못했다' 고 알린다(디자인 개편 검토 09-29). */
export async function getKeywordBoard(regions: string[], page = 1): Promise<KeywordBoard> {
  if (isSampleMode) return sampleKeywordBoard(regions, page);
  const q = new URLSearchParams();
  if (regions.length) q.set("regions", regions.join(","));
  if (page > 1) q.set("page", String(page));
  // Next 의 데이터 캐시에 넣지 않는다 — 지역 조합마다 30만 바이트짜리 항목이 쌓이고 지워지지 않는다(2026-09-29 검토).
  // 백엔드가 이미 캐시(board_cache)에서 내준다.
  const res = await fetch(`${API}/dashboard${q.size ? `?${q}` : ""}`, { cache: "no-store", signal: AbortSignal.timeout(15_000) });
  if (!res.ok) throw new ApiError("/dashboard", res.status);
  return (await res.json()) as KeywordBoard;
}

/** 용어 하나의 쓰임 신호 (사전 화면). regions 를 주면 대시보드 행과 같은 지역만 더한다(없으면 모든 지역).
 *  서버가 없거나 확인 전인 말이면 null — 화면은 사전 항목의 주간 수로 대신한다. */
export async function getTermSignals(termId: string, regions: string[] = []): Promise<KeywordCard | null> {
  if (isSampleMode) return sampleSignals(termId);
  const q = regions.length ? `?regions=${regions.map(encodeURIComponent).join(",")}` : "";
  return apiOr<KeywordCard | null>(`/terms/${encodeURIComponent(termId)}/signals${q}`, null, 300);
}

/** 세계 지도 — 지역 층은 대시보드와 같은 키워드 보드(밈 수·주의·대표 밈, 갱신 시각도 하나), 나라를 건너간 밈은 트렌드 보드의 주제.
 *  api 모드에서 서버가 실패하면 예시로 바꾸지 않고 던진다 → app/map/error.tsx. 실데이터처럼 보이는 2021년 예시가 뜨던 문제(개편 검토). */
export async function getMapData(): Promise<{ keywords: KeywordBoard; board: TrendBoard }> {
  const [keywords, board] = isSampleMode ? [sampleKeywordBoard([], 1, true), SAMPLE_BOARD]
    : await Promise.all([apiNoStore<KeywordBoard>("/dashboard?summary=1"), api<TrendBoard>("/trends/board", 30)]);
  // 지도는 지역 요약과 나라를 건너간 밈(topics)만 쓴다 — 급증 이유(why 737KB)·검색어·목록 셋까지 브라우저로 보내 화면이 1MB 였다
  return {
    keywords: keywords.summary ? { ...keywords, rising: [], fading: [], caution: [] } : keywords,
    board: { ...board, items: [], why: [] },
  };
}

/** 콘텐츠 목록. 못 받으면 null — 예시로 바꾸지 않는다(화면이 '불러오지 못했습니다' 를 낸다). */
export async function getGraphContents(): Promise<GraphContentSummary[] | null> {
  if (isSampleMode) return SAMPLE_GRAPH_CONTENTS;
  // 그래프 API 가 아직 없는 서버(10-01 미리보기)에서는 시험판 예시를 '미리보기' 로 보인다 — API 가 생기면 그대로 실제 데이터
  return (await apiOrNull<GraphContentSummary[]>("/graph/contents", 300)) ?? SAMPLE_GRAPH_CONTENTS.map((c) => ({ ...c, preview: true }));
}

/** 콘텐츠 하나의 나라별 파생 항목. 없으면(404) null, 서버가 답하지 않으면 던진다 → app/graph/[key]/error.tsx. */
export async function getGraphContent(key: string): Promise<GraphContent | null> {
  if (isSampleMode) return SAMPLE_GRAPH[key] ?? null;
  try {
    return await api<GraphContent>(`/graph/content/${encodeURIComponent(key)}`, 300);
  } catch (e) {
    const sample = SAMPLE_GRAPH[key];
    if (sample) return { ...sample, preview: true };   // 그래프 API 가 아직 없는 서버의 미리보기
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}
