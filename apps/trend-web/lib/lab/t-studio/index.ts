/* 디자인 초안 5 '마케터 스튜디오형'(/lab/t-studio)의 입구. 다른 초안과 달리 실데이터가 아니라 예시 데이터로 도는
   한 파일짜리 화면이다(팀원 화면 기획 초안을 다듬은 것). 원본은 source/, 고친 뒤 `python3 source/build.py` 로 다시 만든다.
   문서: docs/디자인-시안/t-studio.md */
export { PROTOTYPE_HTML } from "./prototype-html";

/** 데모 영상 장면 — 화면에서 Alt+숫자로 연다(source/src/app-core.js 의 DEMO_SCENES 와 같다). */
export const DEMO_SCENES = [
  { key: "1", hash: "radar", label: "이번 주 트렌드" },
  { key: "2", hash: "meme-yar", label: "밈 자세히" },
  { key: "3", hash: "studio", label: "콘텐츠 스튜디오" },
  { key: "4", hash: "regions", label: "나라별 비교" },
  { key: "5", hash: "decoder", label: "무슨 뜻이야?" },
] as const;
