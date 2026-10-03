/* 예시 데이터 모드의 키워드 대시보드. 실제 지역 판정·목록 나누기는 백엔드 pipeline/dashboard.py 의 규칙이고,
   여기는 그 규칙을 예시 사전(SAMPLE_RECORDS)에 그대로 옮겨 모델·서버 없이 화면을 열어 보게 할 뿐이다. */
import { termRegions } from "../dictionary/regions";
import { TARGET_REGIONS } from "../reader";
import type { KeywordBoard, KeywordCard, KeywordList, TermRecord } from "../types";
import { SAMPLE_RECORDS } from "./dictionary";

const LIST_MAX = 30;       // 한 쪽에 보이는 수 (백엔드 dashboard.LIST_MAX)
const STALE_DAYS = 90;     // 12주 언급이 0 이고 마지막 쓰임이 이보다 오래되면 '식어 가는' (백엔드 dashboard.STALE_DAYS)
const GENERATED_AT = "2026-09-13T21:10:00Z";
const DIFFUSION_ORDER: Record<string, number> = { spreading: 0, underground: 1, mainstream: 2 };
const LIFECYCLE_ORDER: Record<string, number> = { emerging: 0, rising: 0, peak: 1, steady: 2 };

const hasPath = (url: string) => { try { return !["", "/"].includes(new URL(url).pathname); } catch { return false; } };

function toCard(r: TermRecord): KeywordCard {
  const m = r.meanings.find((x) => !x.valid_to) ?? r.meanings.at(-1);
  const weekly = r.weekly.slice(-12);
  // 홈페이지 주소뿐인 것은 근거가 아니다 — 백엔드 dashboard._has_path 와 같다(예시 모드에서만 근거 없는 추천이 나가던 것, 검토 3차)
  const dated = [...r.evidences].filter((e) => e.kind !== "datalab" && hasPath(e.url)).sort((a, b) => b.observed_at.localeCompare(a.observed_at));
  const recent = dated.slice(0, 5);
  // 커뮤니티 글은 '마지막 쓰임' 으로만 세고 근거로 보이지 않는다 — 백엔드 dashboard.build_card 와 같다(ADR 0003)
  const shown = dated.filter((e) => e.kind !== "community").slice(0, 5);
  return {
    term_id: r.term.term_id, canonical: r.term.canonical, lang: r.term.lang ?? "ko", category: r.category,
    gloss_ko: r.ko?.definition ?? m?.definition ?? "", gloss_en: r.en?.definition ?? m?.definition ?? "",
    regions: termRegions(r), lifecycle: r.term.lifecycle ?? "unknown", diffusion: r.term.diffusion ?? null,
    risk_level: r.term.risk_level ?? null, risk_reasons: r.term.risk_reasons ?? [],
    weekly, mentions_4w: weekly.slice(-4).reduce((a, p) => a + p.count, 0),
    risk_checked_at: r.term.risk_checked_at ?? null,
    search: [], gen_peaks: [], communities: [], tone: { positive: 0, neutral: 0, negative: 0 },
    evidences: shown.map((e) => ({ kind: e.kind, source_domain: e.source_domain, title: e.title ?? e.excerpt ?? "", url: e.url, observed_at: e.observed_at })),
    last_seen: r.term.last_seen ?? null,
    last_used: recent.find((e) => ["community", "news", "short"].includes(e.kind))?.observed_at ?? null,
  };
}

// 마지막 쓰임은 화면의 '마지막 쓰임' 칸과 같은 값. 기준 시각은 예시의 갱신 시각 — 날이 지나도 예시 목록이 바뀌지 않게
const stale = (c: KeywordCard) => {
  const last = c.last_used ?? c.last_seen;
  return !c.weekly.some((p) => p.count) && !!last && Date.parse(GENERATED_AT) - Date.parse(last) > STALE_DAYS * 86_400_000;
};
export const isFadingCard = (c: KeywordCard) => !!c.dated || c.diffusion === "fading" || c.lifecycle === "declining" || c.lifecycle === "dormant" || stale(c);
const flagged = (c: KeywordCard) => c.risk_level === "caution" || c.risk_level === "avoid";

type Lists = Record<KeywordList, KeywordCard[]>;

// 쓰임이 확인된 말 먼저, 원본 언급이 같으면 가장 최근에 쓰인 글 순 (백엔드 dashboard.split 과 같다)
function split(inView: KeywordCard[]): Lists {
  const mentions = (c: KeywordCard) => (c.mentions_mixed ? 0 : c.mentions_4w);
  const byMentions = (a: KeywordCard, b: KeywordCard) => mentions(b) - mentions(a);
  const byConfirmed = (a: KeywordCard, b: KeywordCard) => Number(a.use_confirmed === false) - Number(b.use_confirmed === false);
  const recent = (c: KeywordCard) => [c.last_used, c.last_seen].filter(Boolean).sort().at(-1) ?? "";
  const byRecent = (a: KeywordCard, b: KeywordCard) => recent(b).localeCompare(recent(a));
  const usable = inView.filter((c) => c.risk_level !== "avoid");
  return {
    rising: usable.filter((c) => !isFadingCard(c))
      .sort((a, b) => byConfirmed(a, b) || (DIFFUSION_ORDER[a.diffusion ?? ""] ?? 3) - (DIFFUSION_ORDER[b.diffusion ?? ""] ?? 3) || (LIFECYCLE_ORDER[a.lifecycle] ?? 3) - (LIFECYCLE_ORDER[b.lifecycle] ?? 3) || byMentions(a, b) || byRecent(a, b)),
    fading: usable.filter(isFadingCard).sort((a, b) => byConfirmed(a, b) || byRecent(a, b)),
    caution: inView.filter(flagged).sort((a, b) => Number(a.risk_level !== "avoid") - Number(b.risk_level !== "avoid") || byConfirmed(a, b) || byMentions(a, b) || byRecent(a, b)),
  };
}

export const sampleCards = () => SAMPLE_RECORDS.filter((r) => r.term.status === "verified").map(toCard).filter((c) => c.regions.length);

/** 백엔드 dashboard.board 와 같다: 주의 밈은 쓰이는·식는 목록에도 남고 사용 자제는 주의 목록에만(Plan 04), 목록마다 전체 건수와 page 쪽만 싣는다.
 *  summary 면 지역마다 주의 수·대표 밈(세계 지도). */
export function sampleKeywordBoard(regions: string[], page = 1, summary = false): KeywordBoard {
  const cards = sampleCards();
  const known = [...TARGET_REGIONS, "GLOBAL"];
  const chosen = known.filter((r) => regions.includes(r));
  const picked = chosen.length ? chosen : TARGET_REGIONS;
  const lists = split(cards.filter((c) => c.regions.some((r) => picked.includes(r))));
  const p = Math.max(1, page);
  const cut = (l: KeywordCard[]) => l.slice((p - 1) * LIST_MAX, p * LIST_MAX);
  const top = (l: Lists) => { const c = l.rising[0] ?? l.fading[0]; return c ? { term_id: c.term_id, canonical: c.canonical, lang: c.lang } : null; };
  return {
    generated_at: GENERATED_AT,
    regions: picked,
    counts: { ...Object.fromEntries(known.map((r) => [r, cards.filter((c) => c.regions.includes(r)).length])),
      ALL: cards.filter((c) => c.regions.some((r) => TARGET_REGIONS.includes(r))).length },
    totals: { rising: lists.rising.length, fading: lists.fading.length, caution: lists.caution.length },
    page: p, page_size: LIST_MAX,
    rising: cut(lists.rising), fading: cut(lists.fading), caution: cut(lists.caution),
    ...(summary && { summary: Object.fromEntries(known.map((r) => {
      const l = split(cards.filter((c) => c.regions.includes(r)));
      return [r, { caution: l.caution.length, top: top(l) }];
    })) }),
  };
}

/** 고른 지역의 세 목록 전체(쪽 나누기 없이) — 브리핑이 건수와 앞의 몇 개를 쓴다(백엔드 briefing.build). */
export function sampleLists(regions: string[]): { regions: string[]; generated_at: string } & Lists {
  const chosen = [...TARGET_REGIONS, "GLOBAL"].filter((r) => regions.includes(r));
  const picked = chosen.length ? chosen : TARGET_REGIONS;
  return { regions: picked, generated_at: GENERATED_AT, ...split(sampleCards().filter((c) => c.regions.some((r) => picked.includes(r)))) };
}

/** 백엔드 dashboard.cards_by_id 와 같다 — 최근 변화 행에 단계·쓸 때 조심을 붙인다. */
export function sampleCardsById(ids: string[]): KeywordCard[] {
  const want = new Set(ids);
  return sampleCards().filter((c) => want.has(c.term_id));
}

export function sampleSignals(termId: string): KeywordCard | null {
  const r = SAMPLE_RECORDS.find((x) => x.term.term_id === termId);
  return r && r.term.status === "verified" ? toCard(r) : null;   // 백엔드처럼 확인된 말만 (확인 중인 말은 404)
}
