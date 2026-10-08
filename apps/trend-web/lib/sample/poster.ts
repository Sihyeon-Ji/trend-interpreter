/* 예시 데이터 모드의 포스터 시안 — 그림은 만들지 않고(enabled=false) 구성안만. 백엔드 pipeline/poster.py 의 plan() 을 간단히 옮긴 것이다. */
import type { PosterResult, ProductBrief } from "../types";

const FEELING_MOOD: Record<string, string> = {
  joy: "bright and cheerful", hype: "energetic and dynamic", cute: "soft and cute", funny: "playful and lighthearted",
  relatable: "everyday and familiar", comfort: "cozy and calm", pride: "confident and bold", cool: "cool and sleek",
};

export function samplePoster(market: string, brief: ProductBrief): PosterResult {
  const mood = brief.feelings.map((f) => FEELING_MOOD[f]).filter(Boolean).slice(0, 3);
  return {
    enabled: false,
    plan: { market, product: brief.product, scene: brief.scene ?? "", mood, colors: brief.colors ?? [], aspect_ratio: "4:5",
      prompt: `Promotional poster for ${brief.product}. No text, no people, no characters.` },
    images: [],
  };
}
