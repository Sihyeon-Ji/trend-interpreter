/* 시안 F(에디토리얼) 규칙 — 판(edition) 주소, 호(issue) 이름, 꼭지 나누기, 네이버 검색 추세 계산, 영상 썸네일.
   판정은 여기(데이터 규칙)가 하고 화면은 그리기만 한다. 공용 파일은 읽기만 한다. */
import type { Locale } from "@/lib/i18n";
import { regionLabel } from "@/lib/labels";
import { TARGET_REGIONS } from "@/lib/reader";
import type { GenerationCurve } from "@/lib/trends/types";
import type { KeywordBoard, KeywordCard } from "@/lib/types";
import { fe } from "./f-editorial-copy";

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

/* 꼭지(rubric) — 생애주기·목록 규칙으로만 나눈다. 뜨는 중·절정은 비어도 그렇다고 말한다(마케터에게는 '없음'도 정보다). */
export type RubricKey = "hot" | "peak" | "steady" | "unknown" | "fading" | "caution";
/** total 은 목록 전체 건수(쪽 밖 포함) — 백엔드가 세는 식는 중·조심만 알 수 있다. 나머지는 이 쪽에 실린 수. */
export interface Rubric { key: RubricKey; cards: KeywordCard[]; total: number; alwaysShow: boolean }

export function rubrics(board: KeywordBoard): Rubric[] {
  const hot = board.rising.filter((c) => c.lifecycle === "emerging" || c.lifecycle === "rising");
  const peak = board.rising.filter((c) => c.lifecycle === "peak");
  const unknown = board.rising.filter((c) => c.lifecycle === "unknown");
  const steady = board.rising.filter((c) => !hot.includes(c) && !peak.includes(c) && !unknown.includes(c));
  return [
    { key: "hot", cards: hot, total: hot.length, alwaysShow: true },
    { key: "peak", cards: peak, total: peak.length, alwaysShow: true },
    { key: "steady", cards: steady, total: steady.length, alwaysShow: false },
    { key: "unknown", cards: unknown, total: unknown.length, alwaysShow: false },
    { key: "fading", cards: board.fading, total: board.totals.fading, alwaysShow: false },
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
  return { text: card.gloss_ko };
}

/** 이름·뜻으로 찾기 — 느슨하게(대소문자·공백 무시) */
export function matchCard(card: KeywordCard, q: string): boolean {
  const k = q.toLowerCase().replace(/\s+/g, "");
  if (!k) return false;
  return [card.canonical, card.gloss_ko, card.gloss_en].some((s) => (s ?? "").toLowerCase().replace(/\s+/g, "").includes(k));
}

/* 네이버 검색 추세 — 나이대 곡선을 날짜별로 평균낸 뒤 최근 4주와 이전 4주를 견준다. 곡선이 없으면 null. */
export interface SearchTrend {
  pct: number | null;      // 최근 4주 평균 ÷ 이전 4주 평균 − 1 (%), 이전이 0 이면 null
  weekly: number[];        // 주 평균, 오래된 것부터 (최대 26주)
  latest: number;          // 최근 4주 평균
  previous: number;        // 이전 4주 평균
}

const avg = (xs: number[]) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0);

export function searchTrend(curves: GenerationCurve[]): SearchTrend | null {
  const byDate = new Map<string, number[]>();
  for (const c of curves) for (const [d, v] of c.points) {
    const a = byDate.get(d) ?? [];
    a.push(v);
    byDate.set(d, a);
  }
  const dates = [...byDate.keys()].sort();
  if (dates.length < 56) return null;
  const mean = dates.map((d) => avg(byDate.get(d)!));
  const latest = avg(mean.slice(-28));
  const previous = avg(mean.slice(-56, -28));
  const pct = previous >= 1 ? Math.round(((latest - previous) / previous) * 100) : null;
  const weekly: number[] = [];
  for (let end = mean.length; end > 0 && weekly.length < 26; end -= 7) weekly.unshift(avg(mean.slice(Math.max(0, end - 7), end)));
  return { pct, weekly, latest, previous };
}

/** "+46%" / "−9%" — 기호는 글자로, 색으로 방향을 말하지 않는다 */
export const fmtPct = (pct: number) => (pct > 0 ? `+${pct}%` : pct < 0 ? `−${Math.abs(pct)}%` : "0%");

/** 규칙이 남긴 조심 이유에서 커뮤니티 글 인용과 사이트 이름을 뗀다 — 커뮤니티 글은 신호로만 쓰고 화면에 내지 않는다(자료 정책).
 *  "부정적으로 쓰인 근거가 40% — 예: “…” (bsky.app)" → "부정적으로 쓰인 근거가 40%",  "위험 유형이 붙은 근거 3건: “…” (bsky.app)" → "위험 유형이 붙은 근거 3건" */
export function cleanReason(s: string): string {
  return s
    .replace(/\s*[—–-]\s*예\s*:[\s\S]*$/u, "")
    .replace(/\s*:\s*[“"'][\s\S]*$/u, "")
    .replace(/\s*\([a-z0-9.-]+\.[a-z]{2,}\)\s*$/iu, "")
    .trim()
    .replace(/[:：]$/u, "");
}

/** 나라별 차이 문장에서 백엔드의 자리 표시("근거 부족: 확인되지 않음")는 문장이 아니므로 내지 않는다 */
export const isPlaceholder = (s: string | null | undefined) => !s || /^근거 부족/u.test(s) || /^not (enough|confirmed)/iu.test(s) || /^insufficient/iu.test(s);

/* 영상 썸네일 — 유튜브 주소에 영상 id 가 있을 때만. 파일을 받아 두지 않고 유튜브가 주는 그림을 그대로 잇는다. */
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
