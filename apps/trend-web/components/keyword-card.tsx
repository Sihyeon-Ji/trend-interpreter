import Link from "next/link";
import { Sparkline } from "@/components/sparkline";
import { t, type Locale } from "@/lib/i18n";
import { L, fmtInt, listJoin, regionLabel, sourceName } from "@/lib/labels";
import type { KeywordCard, SearchHit } from "@/lib/types";
import { cn } from "@/lib/utils";

/** "대만 인기 검색어 3위 · “傻眼貓咪 意思” · 2만+" / "#3 trending search in Taiwan · …" */
export function searchLine(locale: Locale, h: SearchHit): string {
  const where = regionLabel(locale, h.region);
  const tail = `${h.query ? ` · “${h.query}”` : ""}${h.traffic ? ` · ${h.traffic}` : ""}`;
  if (locale === "ko") return `${where} 인기 검색어${h.rank ? ` ${h.rank}위` : ""}${tail}`;
  return `${h.rank ? `#${h.rank} ` : ""}trending search in ${where}${tail}`;
}

/** 쓸 때 주의·사용 자제만 표시한다. 없음·판단 보류는 칸을 내지 않는다(판정은 백엔드 pipeline/risk.py). */
export function riskOf(card: Pick<KeywordCard, "risk_level">) {
  return card.risk_level === "caution" || card.risk_level === "avoid" ? card.risk_level : null;
}

/* 대시보드 카드 한 장. 흰 바탕·hairline 테두리, 그림자·색 띠 없이 글자로만 구분한다. */
export function KeywordCardView({ card, locale }: { card: KeywordCard; locale: Locale }) {
  const labels = L(locale);
  const risk = riskOf(card);
  const hit = card.search[0];
  const stage = [card.diffusion ? t(locale, `diffusion_${card.diffusion}`) : null, labels.lifecycle[card.lifecycle]].filter(Boolean).join(" · ");
  return (
    <article className="flex flex-col gap-2 rounded-lg border border-hairline p-4">
      <div className="flex items-start justify-between gap-3">
        <Link href={`/dictionary/${card.term_id}`} className="min-w-0 break-words text-[16px] font-semibold text-ink hover:underline">{card.canonical}</Link>
        {risk && (
          <span className={cn("shrink-0 rounded border px-1.5 text-[12px] leading-[20px]", risk === "avoid" ? "border-ink font-medium text-ink" : "border-hairline-strong text-charcoal")}>
            {t(locale, `risk_${risk}`)}
          </span>
        )}
      </div>
      <p className="line-clamp-2 text-[14px] leading-[1.55] text-charcoal">{locale === "ko" ? card.gloss_ko : card.gloss_en}</p>
      <p className="text-[12px] text-steel">{stage}</p>
      {card.weekly.some((p) => p.count > 0) && (
        <div className="flex items-end gap-3">
          <Sparkline points={card.weekly} width={120} height={28} />
          <span className="text-[12px] text-steel">{t(locale, "dash_mentions_4w")} <span className="tabular-nums text-charcoal">{fmtInt(card.mentions_4w)}</span></span>
        </div>
      )}
      {hit && <p className="text-[12px] text-charcoal">{searchLine(locale, hit)}</p>}
      {!hit && locale === "ko" && card.search_trend && <p className="line-clamp-2 text-[12px] text-charcoal">{sourceName(locale, "datalab.naver.com")}: {card.search_trend}</p>}
      {card.communities.length > 0 && (
        <p className="text-[12px] text-steel">{t(locale, "dash_seen_on")}: {card.communities.slice(0, 3).map((c) => `${sourceName(locale, c.domain)} ${c.count}`).join(" · ")}</p>
      )}
      <p className="mt-auto pt-1 text-[12px] text-steel">{t(locale, "dash_used_in")}: {listJoin(locale, card.regions.map((r) => regionLabel(locale, r)))}</p>
    </article>
  );
}
