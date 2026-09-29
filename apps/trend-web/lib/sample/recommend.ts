/* 예시 데이터 모드의 밈 추천. 규칙은 백엔드 pipeline/recommend.py 의 score() 를 그대로 옮긴 것이고,
   표제어의 쓰임 낱말(fit 단계가 로컬 Gemma 로 붙이는 값)은 예시 사전 몇 개에 손으로 붙여 두었다.
   제품 설명도 모델 없이 고정 예시(SAMPLE_BRIEF)라, 화면이 "예시 제품으로 보여 준다" 고 알린다. */
import type { CampaignTone, Feeling, FitCategory, KeywordCard, ProductBrief, RecommendItem, RecommendResult } from "../types";
import { sampleKeywordBoard } from "./keyword-board";

type Voice = "wholesome" | "playful" | "edgy" | "crude";
interface Fit { feelings: Feeling[]; fits: FitCategory[]; any_category: boolean; voice: Voice }

export const SAMPLE_BRIEF: ProductBrief = {
  product: "여름 한정 아이스 흑당 라떼", category: "food_drink", feelings: ["joy", "relatable", "comfort"],
  values: ["시원함", "달콤함", "여름 한정"], scene: "더운 오후 카페에서 한숨 돌릴 때", colors: ["갈색", "흰색"], avoid: [],
};

const SAMPLE_FIT: Record<string, Fit> = {
  t_luckyvicky: { feelings: ["joy", "comfort"], fits: [], any_category: true, voice: "wholesome" },
  t_wonyoung: { feelings: ["joy", "pride"], fits: ["fashion_beauty"], any_category: true, voice: "wholesome" },
  t_jeomechu: { feelings: ["relatable"], fits: ["food_drink"], any_category: false, voice: "playful" },
  t_jamanchu: { feelings: ["romance"], fits: [], any_category: false, voice: "playful" },
  t_aljal: { feelings: ["relatable", "funny"], fits: [], any_category: true, voice: "playful" },
  t_sixseven: { feelings: ["funny", "hype"], fits: [], any_category: true, voice: "playful" },
  t_aurafarming: { feelings: ["cool", "hype"], fits: ["fashion_beauty"], any_category: false, voice: "edgy" },
  t_oshikatsu: { feelings: ["hype", "pride"], fits: ["entertainment"], any_category: false, voice: "wholesome" },
  t_skibidi: { feelings: ["funny"], fits: [], any_category: true, voice: "playful" },
};

const TONES: Record<CampaignTone, [Voice[], Feeling[]]> = {
  friendly: [["wholesome", "playful"], ["joy", "cute", "relatable", "comfort"]],
  witty: [["wholesome", "playful", "edgy"], ["funny", "sarcasm", "relatable", "surprise"]],
  premium: [["wholesome"], ["cool", "pride", "romance", "nostalgia"]],
};
const DIFFUSION_BONUS: Record<string, number> = { spreading: 2, underground: 1, mainstream: 0.5, fading: -2 };
const LIFECYCLE_BONUS: Record<string, number> = { emerging: 1, rising: 1, peak: 0.5, declining: -1, dormant: -3 };
const MIN_FIT = 2, MIN_SCORE = 2, TOP = 5;
const USAGE = ["community", "news", "short"];
const SCRIPT: Record<string, RegExp> = { KR: /[가-힣]/, JP: /[\u3040-\u30ff\u4e00-\u9fff]/, TW: /[\u4e00-\u9fff]/, HK: /[\u4e00-\u9fff]/, TH: /[\u0e00-\u0e7f]/ };
const writable = (name: string, region: string) => /^[\x00-\x7f\u00c0-\u024f\u1e00-\u1eff]+$/.test(name) || !!SCRIPT[region]?.test(name);

function score(brief: ProductBrief, fit: Fit, c: KeywordCard, tone: CampaignTone): [number, boolean, Feeling[]] | null {
  const [voices, liked] = TONES[tone];
  if (c.risk_level === "avoid" || fit.voice === "crude" || !voices.includes(fit.voice)) return null;
  const cat = fit.fits.includes(brief.category);
  const shared = brief.feelings.filter((f) => fit.feelings.includes(f)).slice(0, 3);
  const rel = (cat ? 3 : fit.any_category ? 1 : 0) + 2 * shared.length;
  if (rel < MIN_FIT) return null;
  let s = rel + fit.feelings.filter((f) => liked.includes(f)).length;
  s += (DIFFUSION_BONUS[c.diffusion ?? ""] ?? 0) + (LIFECYCLE_BONUS[c.lifecycle] ?? 0);
  s += c.risk_level === "caution" ? -2 : c.risk_level == null ? -0.5 : 0;
  return s >= MIN_SCORE ? [s, cat, shared] : null;
}

export function sampleRecommend(regions: string[], tone: CampaignTone): RecommendResult {
  const board = sampleKeywordBoard(regions);
  const cards = [...new Map([...board.rising, ...board.fading, ...board.caution].map((c) => [c.term_id, c])).values()];
  const scored = cards.flatMap((c) => {
    const fit = SAMPLE_FIT[c.term_id];
    const got = fit ? score(SAMPLE_BRIEF, fit, c, tone) : null;
    return got ? [{ c, s: got[0], cat: got[1], shared: got[2], any: fit.any_category }] : [];
  }).sort((a, b) => b.s - a.s || b.c.mentions_4w - a.c.mentions_4w || a.c.canonical.localeCompare(b.c.canonical));
  // 근거 링크 두 건 — 쓰임 글이 먼저, 같은 주소는 한 번만. 링크가 없는 것은 추천하지 않는다(백엔드 recommend._links 와 같다)
  const links = (c: KeywordCard) => [...c.evidences].sort((a, b) => Number(!USAGE.includes(a.kind)) - Number(!USAGE.includes(b.kind)))
    .filter((e, i, all) => all.findIndex((x) => x.url === e.url) === i).slice(0, 2);
  const items: RecommendItem[] = scored.filter(({ c }) => links(c).length).slice(0, TOP).map(({ c, s, cat, shared, any }) => ({
    term_id: c.term_id, canonical: c.canonical, gloss_ko: c.gloss_ko, gloss_en: c.gloss_en, regions: c.regions,
    diffusion: c.diffusion ?? null, lifecycle: c.lifecycle, risk_level: c.risk_level ?? null, risk_reasons: c.risk_reasons,
    matched_category: cat, any_category: any, matched_feelings: shared, local_region: null, local_note: null,
    // 예시 모드: 그 지역의 글자로 쓴 표기(또는 로마자)가 있는 곳만 — 백엔드 generate.writable 의 간단한 판
    write_regions: board.regions.filter((r) => c.regions.includes(r) && writable(c.canonical, r)), score: Math.round(s * 100) / 100,
    evidences: links(c),
  }));
  return { brief: SAMPLE_BRIEF, brief_source: "sample", regions: board.regions, tone, items, considered: scored.length,
           untagged: cards.filter((c) => !SAMPLE_FIT[c.term_id]).length };
}
