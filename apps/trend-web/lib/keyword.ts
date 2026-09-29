/* 키워드 카드·추천·사전 항목이 함께 쓰는 표시 규칙. 판정은 백엔드가 하고 여기서는 글로만 옮긴다. */
import { t, type Locale } from "@/lib/i18n";
import { L, regionLabel } from "@/lib/labels";
import type { GenPeak, KeywordCard, SearchHit } from "@/lib/types";

/** "대만 인기 검색어 3위 · “傻眼貓咪 意思” · 2만+" / "#3 trending search in Taiwan · …" */
export function searchLine(locale: Locale, h: SearchHit): string {
  const where = regionLabel(locale, h.region);
  const tail = `${h.query ? ` · “${h.query}”` : ""}${h.traffic ? ` · ${h.traffic}` : ""}`;
  if (locale === "ko") return `${where} 인기 검색어${h.rank ? ` ${h.rank}위` : ""}${tail}`;
  return `${h.rank ? `#${h.rank} ` : ""}trending search in ${where}${tail}`;
}

/** 표시할 리스크. 주의·사용 자제와, 근거가 모자라 판단을 보류한 것('근거 부족')을 보인다 — 보류를 '문제 없음' 처럼 숨기면
 *  검사하지 못한 말이 안전해 보인다(Plan 03 규칙표, 2026-09-29 검토). 문제 없음은 칸을 내지 않는다. 판정은 백엔드 pipeline/risk.py. */
export function riskOf(card: { risk_level?: KeywordCard["risk_level"]; risk_checked_at?: string | null }): "caution" | "avoid" | "unknown" | null {
  if (card.risk_level === "caution" || card.risk_level === "avoid") return card.risk_level;
  return card.risk_level == null && card.risk_checked_at ? "unknown" : null;   // 검사했는데 근거가 모자란 것만. 검사 전이면 칸을 내지 않는다
}

/** "20대 2025.11 · 30대 2026.02" — 네이버 데이터랩 연령대별 검색 정점 */
export function peaksLine(locale: Locale, peaks: GenPeak[]): string {
  const labels = L(locale);
  return peaks.slice(0, 4).map((p) => `${labels.generation[p.generation as keyof typeof labels.generation] ?? p.generation} ${p.date.slice(0, 7).replace("-", ".")}`).join(" · ");
}

/** 단계 한 줄. 영어에서 '식상' 과 '줄어드는 중' 이 둘 다 fading 이라 'Fading · fading' 이 되던 것을 한 번만. */
export function stageLine(locale: Locale, card: Pick<KeywordCard, "diffusion" | "lifecycle">): string {
  const labels = L(locale);
  const dif = card.diffusion ? t(locale, `diffusion_${card.diffusion}`) : null;
  const life = labels.lifecycle[card.lifecycle];
  return (dif && dif.toLowerCase() === life.toLowerCase() ? [dif] : [dif, life]).filter(Boolean).join(" · ");
}
