/* 예시 모드의 '최근 변화'와 나라 화면의 '검색이 늘어난 이유'. 모델·서버 없이 화면을 열어 보게 할 뿐이다.
   이유 문장은 예시 보드(trend-board.ts)의 한 줄 설명에 적힌 것만 옮겼다 — 없는 사실을 지어내지 않는다.
   원인을 찾지 못한 것(trigger unknown)도 하나 넣어, 화면이 그런 행을 빼고 건수만 알리는지 보이게 한다. */
import type { TrendWhy, UpdateFeed, UpdateItem } from "../trends/types";
import { SAMPLE_BOARD } from "./trend-board";

const at = (hoursBefore: number) => new Date(Date.parse(SAMPLE_BOARD.generated_at) - hoursBefore * 3_600_000).toISOString();

function why(term: string, region: string, date: string, trigger: TrendWhy["trigger"], ko: string, en: string, first_signal: string | null = null): TrendWhy {
  return { term, region, date, why_now: { ko, en }, trigger, actors: [], first_signal, confidence: trigger === "unknown" ? 0.2 : 0.7,
    evidence_counts: {}, evidence: [], updated_at: SAMPLE_BOARD.generated_at };
}

export const SAMPLE_WHY: TrendWhy[] = [
  why("沖縄県知事選挙", "JP", "2026-09-13", "event", "9월 13일 오키나와 지사 선거가 치러지며 검색이 늘었습니다.", "Searches rose as the Okinawa governor election took place on Sep 13."),
  why("八つ墓村", "JP", "2026-09-14", "release", "9월 18일 개봉하는 영화의 예고편이 인기 영상에 오르며 검색이 늘었습니다.", "Searches rose as the trailer for the film opening Sep 18 became a trending video."),
  why("森本レオ", "JP", "2026-09-13", "unknown", "", ""),
  why("삐에로 밈", "KR", "2026-09-13", "meme", "말끝에 '삐'를 붙이는 놀이가 8월 13일 커뮤니티 글에서 시작해 퍼지며 검색이 늘었습니다.",
    "Searches rose as a game of adding 삐 to word endings spread from an Aug 13 community post.", "2026-08-13"),
  why("ธี่หยด", "TH", "2026-09-14", "release", "공포 영화 신작 예고편이 9월 14일 인기 영상에 오르며 검색이 늘었습니다.", "Searches rose as a horror sequel trailer became a trending video on Sep 14."),
];

const reason = (term: string) => {
  const w = SAMPLE_WHY.find((x) => x.term === term);
  return w && w.trigger !== "unknown" ? w.why_now : null;
};

const ITEMS: UpdateItem[] = [
  { kind: "spike", at: at(1), label: "沖縄県知事選挙", region: "JP", detail: "event", reason: reason("沖縄県知事選挙") },
  { kind: "verified", at: at(2), label: "推し活", term_id: "t_oshikatsu", detail: "verified_auto" },
  { kind: "spike", at: at(3), label: "八つ墓村", region: "JP", detail: "release", reason: reason("八つ墓村") },
  { kind: "verified", at: at(6), label: "aura farming", term_id: "t_aurafarming", detail: "verified_auto" },
  { kind: "spike", at: at(20), label: "삐에로 밈", region: "KR", detail: "meme", reason: reason("삐에로 밈") },
  { kind: "verified", at: at(27), label: "원영적 사고", term_id: "t_wonyoung", detail: "verified_human" },
];

/** 백엔드 GET /updates 와 같은 모양 */
export function sampleUpdateFeed(): UpdateFeed {
  const counts: Record<string, number> = { verified: 0, meaning_changed: 0, spike: 0 };
  for (const i of ITEMS) counts[i.kind] += 1;
  return { items: ITEMS, counts, total: ITEMS.length };
}
