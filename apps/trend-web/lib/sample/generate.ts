/* 예시 데이터 모드의 만들기 결과. 백엔드 pipeline/generate.sample 과 같은 고정 예시 — 모델 없이 화면과 e2e 가 끝까지 돈다. */
import type { CampaignTone, GenerationResult } from "../types";
import { SAMPLE_RECORDS } from "./dictionary";

export function sampleGenerate(termIds: string[], region: string, tone: CampaignTone): GenerationResult {
  const names = termIds.map((id) => SAMPLE_RECORDS.find((r) => r.term.term_id === id && r.term.status === "verified")?.term.canonical).filter((x): x is string => !!x);
  const name = names[0] ?? "럭키비키";
  return {
    // 예시 글은 한국어다 — 목표 지역의 말이라고 적지 않는다(백엔드 generate.sample 과 같다)
    region, language: "ko", tone, memes: names.length ? names : [name], model_calls: 0, source: "sample", dropped: [],
    copies: [
      { platform: "instagram", text: `더운 오후엔 ${name}! 여름 한정 아이스 흑당 라떼로 기분 전환해요 ☕`, hashtags: ["여름한정", "흑당라떼", name.replace(/[\s\-]/g, "")], note_ko: `'${name}' 을 제품의 기분 전환 순간에 붙였다` },
      { platform: "instagram", text: `오늘의 ${name}은 시원한 한 잔. 여름에만 만나요`, hashtags: ["아이스라떼", "여름메뉴"], note_ko: "한정판을 강조" },
      { platform: "x", text: `${name} 필요한 오후, 흑당 라떼 한 잔이면 충분`, hashtags: [], note_ko: "짧은 공감형" },
      { platform: "x", text: `여름 한정이라 더 ${name}. 이번 주까지!`, hashtags: [], note_ko: "마감 강조" },
    ],
    script: {
      title: `${name} 한 잔`, duration_s: 15, note_ko: "지친 오후 → 한 모금 → 밈 자막으로 반전",
      scenes: [
        { start_s: 0, end_s: 4, visual: "더위에 지친 얼굴", caption: "오후 3시…", line: "" },
        { start_s: 4, end_s: 10, visual: "라떼를 한 모금", caption: `${name}!`, line: "이거면 돼" },
        { start_s: 10, end_s: 15, visual: "제품 클로즈업", caption: "여름 한정", line: "" },
      ],
    },
    thumbnail: { headline: `${name} 한 잔`, layout: "왼쪽 제품, 오른쪽 큰 문구", colors: ["갈색", "흰색"], subject: "제품을 화면 왼쪽 3분의 1", note_ko: "문구는 두 줄 이내" },
  };
}
