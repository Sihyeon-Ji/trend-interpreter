import Link from "next/link";
import { Sparkline } from "@/components/sparkline";
import { t, type Locale } from "@/lib/i18n";
import { L, fmtInt, listJoin, regionLabel, sourceName } from "@/lib/labels";
import type { GenPeak, KeywordCard, SearchHit } from "@/lib/types";
import { cn } from "@/lib/utils";

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

/* 대시보드 카드 한 장. 흰 바탕·hairline 테두리, 그림자·색 띠 없이 글자로만 구분한다. */
export function KeywordCardView({ card, locale }: { card: KeywordCard; locale: Locale }) {
  const risk = riskOf(card);
  const hit = card.search[0];
  const stage = stageLine(locale, card);
  return (
    <article className="flex flex-col gap-2 rounded-lg border border-hairline p-4">
      <div className="flex items-start justify-between gap-3">
        <Link href={`/dictionary/${card.term_id}`} className="min-w-0 break-words text-[16px] font-semibold text-ink hover:underline">{card.canonical}</Link>
        {risk && (
          <span className={cn("shrink-0 rounded border px-1.5 text-[12px] leading-[20px]",
            risk === "avoid" ? "border-ink font-medium text-ink" : risk === "caution" ? "border-hairline-strong text-charcoal" : "border-hairline text-steel")}>
            {t(locale, `risk_${risk}`)}
          </span>
        )}
      </div>
      <p className="line-clamp-2 text-[14px] leading-[1.55] text-charcoal">{locale === "ko" ? card.gloss_ko : card.gloss_en}</p>
      <p className="text-[12px] text-steel">{stage}</p>
      {card.weekly.some((p) => p.count > 0) && (
        <div className="flex items-end gap-3">
          <Sparkline points={card.weekly} width={120} height={28} label={t(locale, "spark_label").replace("{n}", String(card.weekly.length)).replace("{last}", String(card.weekly.at(-1)?.count ?? 0)).replace("{max}", String(Math.max(0, ...card.weekly.map((p) => p.count))))} />
          <span className="text-[12px] text-steel">{t(locale, "dash_mentions_4w")} <span className="tabular-nums text-charcoal">{fmtInt(card.mentions_4w)}</span></span>
        </div>
      )}
      {hit && <p className="text-[12px] text-charcoal">{searchLine(locale, hit)}</p>}
      {!hit && card.gen_peaks.length > 0 && <p className="text-[12px] text-charcoal">{t(locale, "sig_gen_peaks")}: {peaksLine(locale, card.gen_peaks)}</p>}
      {card.communities.length > 0 && (
        <p className="text-[12px] text-steel">{t(locale, "dash_seen_on")}: {card.communities.slice(0, 3).map((c) => `${sourceName(locale, c.domain)} ${c.count}`).join(" · ")}</p>
      )}
      <p className="mt-auto pt-1 text-[12px] text-steel">{t(locale, "dash_used_in")}: {listJoin(locale, card.regions.map((r) => regionLabel(locale, r)))}</p>
    </article>
  );
}
