/* 예시 데이터 모드의 트렌드 브리핑 — 백엔드 pipeline/briefing.py 의 build 와 같은 규칙을 예시 대시보드 목록에 옮긴다.
   요약은 만들지 않는다(모델 없음) — 화면이 규칙 문장을 쓴다. */
import type { Briefing } from "../types";
import { sampleLists } from "./keyword-board";

const TOP = 5;   // 백엔드 briefing.BRIEF_TOP

export function sampleBriefing(regions: string[]): Briefing {
  const l = sampleLists(regions);
  const useNow = l.rising.filter((c) => c.risk_level === "none");
  const careful = l.rising.filter((c) => c.risk_level === "caution");
  const avoid = l.caution.filter((c) => c.risk_level === "avoid");
  return {
    generated_at: l.generated_at,
    regions: l.regions,
    counts: { rising: l.rising.length, use_now: useNow.length, careful: careful.length,
      undecided: l.rising.filter((c) => !c.risk_level).length, avoid: avoid.length, fading: l.fading.length },
    use_now: useNow.slice(0, TOP), careful: careful.slice(0, TOP), avoid: avoid.slice(0, TOP), fading: l.fading.slice(0, TOP),
    summary: null, summary_source: "none",
  };
}
