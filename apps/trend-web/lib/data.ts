/* 데이터 접근 계층. 지금은 예시 데이터, DATA_MODE=api 면 Python(ADK) 서비스에서 가져온다.
   화면은 이 함수들만 부른다 — 소스가 바뀌어도 화면은 안 바뀌게. */
import { SAMPLE_BOARD } from "./sample/trend-board";
import type { GenerationCurve, Meta, TrendBoard, TrendWhy, UpdateItem } from "./trends/types";
import type { KeywordBoard, KeywordCard, PipelineStage, ReviewItem, TermRecord } from "./types";
import type { Locale } from "./i18n";
import type { Reader } from "./reader";
import { SAMPLE_COPY, SAMPLE_COPY_EN, SAMPLE_QUEUE, SAMPLE_RECORDS, SAMPLE_REWRITES, SAMPLE_STAGES } from "./sample/dictionary";
import { explainMessage, type ExplainResult } from "./explain";
import { sampleKeywordBoard, sampleSignals } from "./sample/keyword-board";

export const isSampleMode = process.env.DATA_MODE !== "api";
const API = process.env.TREND_API_URL ?? "http://localhost:8080";

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

export async function getTermRecords(): Promise<TermRecord[]> {
  return isSampleMode ? SAMPLE_RECORDS : apiOr<TermRecord[]>("/terms", SAMPLE_RECORDS);
}

export async function getTermRecord(termId: string): Promise<TermRecord | null> {
  const sample = SAMPLE_RECORDS.find((r) => r.term.term_id === termId) ?? null;
  if (isSampleMode) return sample;
  try {
    return await api<TermRecord | null>(`/terms/${encodeURIComponent(termId)}`);
  } catch (e) {
    // 서버가 "없다/제외됐다"(404)고 하면 예시 데이터로 되살리지 않는다 → 404 페이지. 서버가 죽었을 때만 예시로 내려간다
    if (e instanceof ApiError && e.status === 404) return null;
    return sample;
  }
}

export async function getPipelineStages(): Promise<PipelineStage[]> {
  return isSampleMode ? SAMPLE_STAGES : apiOr<PipelineStage[]>("/pipeline/stages", SAMPLE_STAGES, 30);
}

export async function getReviewQueue(): Promise<ReviewItem[]> {
  return isSampleMode ? SAMPLE_QUEUE : apiOr<ReviewItem[]>("/review/queue", SAMPLE_QUEUE, 30);
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
    // 서버 매칭은 확인 중(needs_review)인 용어도 돌려준다 → 공개 목록(/terms 는 verified 만)이 아니라 전체로 풀어야 '뜻을 확인하는 중' 안내가 나온다
    const records = await apiOr<TermRecord[]>("/terms?status=all", await getTermRecords());
    const picked = term_ids.map((id) => records.find((r) => r.term.term_id === id)).filter((r): r is TermRecord => !!r);
    return explainMessage(text, picked, locale, plain, reader);
  }
  const plain = SAMPLE_REWRITES[locale][text.trim()] ?? null;
  return explainMessage(text, SAMPLE_RECORDS, locale, plain, reader);
}

export async function getTrendBoard(): Promise<TrendBoard> {
  if (isSampleMode) return SAMPLE_BOARD;
  const b = await apiOr<TrendBoard>("/trends/board", SAMPLE_BOARD, 30);
  return { ...b, why: b.why ?? [] };
}

export async function getMeta(): Promise<Meta | null> {
  return isSampleMode ? null : apiOr<Meta | null>("/meta", null, 30);
}

export async function getUpdates(hours = 48): Promise<UpdateItem[]> {
  return isSampleMode ? [] : apiOr<UpdateItem[]>(`/updates?hours=${hours}`, [], 30);
}

export interface CountryPage { region: string; items: TrendBoard["items"]; why: TrendWhy[]; terms: TermRecord[]; generation_share: Record<string, number>; updated_at: string | null }

export async function getCountryPage(region: string): Promise<CountryPage> {
  if (isSampleMode) {
    const items = SAMPLE_BOARD.items.filter((i) => i.region === region);
    const terms = SAMPLE_RECORDS.filter((r) => r.usage.some((u) => u.segment.region === region));
    const share: Record<string, number> = {};
    for (const r of terms) for (const u of r.usage) if (u.segment.region === region) share[u.segment.generation] = (share[u.segment.generation] ?? 0) + u.share;
    const total = Object.values(share).reduce((a, b) => a + b, 0) || 1;
    for (const k of Object.keys(share)) share[k] = Math.round((share[k] / total) * 1000) / 1000;
    return { region, items, why: [], terms, generation_share: share, updated_at: SAMPLE_BOARD.generated_at };
  }
  return apiOr<CountryPage>(`/countries/${encodeURIComponent(region)}`, { region, items: [], why: [], terms: [], generation_share: {}, updated_at: new Date(0).toISOString() } as CountryPage, 30);  // 백엔드가 꺼져 있으면 500 대신 빈 페이지 (getTrendBoard 등과 같은 폴백)
}

export async function getGenerationCurves(termId: string): Promise<GenerationCurve[]> {
  return isSampleMode ? [] : apiOr<GenerationCurve[]>(`/terms/${encodeURIComponent(termId)}/generations`, [], 300);
}

export interface ReviewStats { verified_auto: number; verified_human: number; needs_review: number; rejected: number }

/** 자동 확인 vs 사람 검수 비율 — 관리자 화면의 '자동화 정도' 표시. */
export async function getReviewStats(): Promise<ReviewStats> {
  if (isSampleMode) {
    const cur = SAMPLE_RECORDS.map((r) => r.meanings.find((m) => !m.valid_to) ?? r.meanings.at(-1)).filter(Boolean);
    const count = (v: string) => cur.filter((m) => m!.verification === v).length;
    return { verified_auto: count("verified_auto"), verified_human: count("verified_human"), needs_review: SAMPLE_QUEUE.length, rejected: count("rejected") };
  }
  return api<ReviewStats>("/review/stats");
}

/** 키워드 대시보드 (Plan 04). regions 가 비면 목표 지역 전체. 지역 판정과 목록 나누기는 백엔드 규칙이 한다. */
export async function getKeywordBoard(regions: string[]): Promise<KeywordBoard> {
  const fallback = sampleKeywordBoard(regions);
  if (isSampleMode) return fallback;
  const q = regions.length ? `?regions=${regions.map(encodeURIComponent).join(",")}` : "";
  // Next 의 데이터 캐시에 넣지 않는다 — 지역 조합마다 30만 바이트짜리 항목이 쌓이고 지워지지 않는다(2026-09-29 검토).
  // 백엔드가 이미 캐시(board_cache)에서 내준다.
  try {
    const res = await fetch(`${API}/dashboard${q}`, { cache: "no-store" });
    return res.ok ? ((await res.json()) as KeywordBoard) : fallback;
  } catch {
    return fallback;
  }
}

/** 용어 하나의 쓰임 신호 (사전 화면). 서버가 없으면 신호 칸을 내지 않는다. */
export async function getTermSignals(termId: string): Promise<KeywordCard | null> {
  return isSampleMode ? sampleSignals(termId) : apiOr<KeywordCard | null>(`/terms/${encodeURIComponent(termId)}/signals`, null, 300);
}
