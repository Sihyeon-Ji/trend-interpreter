import Link from "next/link";
import { Sparkline } from "@/components/sparkline";
import { RiskCell, StageCell } from "@/components/term-status";
import { t, type Locale } from "@/lib/i18n";
import { langTag } from "@/lib/lang";
import { fmtDate, fmtInt, regionLabel, sourceName } from "@/lib/labels";
import type { KeywordCard } from "@/lib/types";

const lastUsed = (c: KeywordCard) => c.last_used ?? c.last_seen ?? null;
const gloss = (c: KeywordCard, locale: Locale) => (locale === "ko" ? c.gloss_ko : c.gloss_en);

function Trend({ card, locale }: { card: KeywordCard; locale: Locale }) {
  const max = Math.max(0, ...card.weekly.map((p) => p.count));
  return (
    <div className="flex items-center justify-end gap-3">
      {max > 0 && (
        <Sparkline points={card.weekly} width={84} height={24}
          label={t(locale, "spark_label").replace("{n}", String(card.weekly.length)).replace("{last}", String(card.weekly.at(-1)?.count ?? 0)).replace("{max}", String(max))} />
      )}
      <span className="w-10 text-right tabular-nums text-[14px] text-ink">{fmtInt(card.mentions_4w)}</span>
    </div>
  );
}

/* 대시보드 목록. 데스크톱은 표, 휴대폰은 한 줄씩 — 카드 모자이크를 쓰지 않는다. 표제어를 누르면 사전 항목(뜻·근거·신호). */
export function KeywordTable({ cards, locale }: { cards: KeywordCard[]; locale: Locale }) {
  const where = (c: KeywordCard) => c.communities.slice(0, 2).map((s) => sourceName(locale, s.domain));
  return (
    <>
      <div className="hidden overflow-x-auto md:block">
        <table className="w-full min-w-[960px] border-collapse text-left">
          <caption className="sr-only">{t(locale, "dash_table_caption")}</caption>
          <thead>
            <tr className="border-b border-hairline text-[13px] text-steel">
              <th scope="col" className="py-2.5 pr-4 font-medium">{t(locale, "dash_col_keyword")}</th>
              <th scope="col" className="w-[190px] py-2.5 pr-4 font-medium">{t(locale, "dash_col_stage")}</th>
              <th scope="col" className="w-[150px] py-2.5 pr-4 text-right font-medium">{t(locale, "dash_mentions_4w")}</th>
              <th scope="col" className="w-[110px] py-2.5 pr-4 font-medium">{t(locale, "dash_last_used")}</th>
              <th scope="col" className="w-[150px] py-2.5 pr-4 font-medium">{t(locale, "dash_seen_on")}</th>
              <th scope="col" className="w-[120px] py-2.5 font-medium">{t(locale, "dash_col_risk")}</th>
            </tr>
          </thead>
          <tbody>
            {cards.map((c) => (
              <tr key={c.term_id} className="border-b border-hairline align-top hover:bg-surface-soft">
                <td className="max-w-0 py-3 pr-4">
                  <Link href={`/dictionary/${c.term_id}`} lang={langTag(c.lang)} className="text-[15px] font-semibold text-ink hover:underline">{c.canonical}</Link>
                  <p className="mt-0.5 truncate text-[13px] text-charcoal" title={gloss(c, locale)}>{gloss(c, locale)}</p>
                  <p className="mt-0.5 truncate text-[12px] text-steel">{c.regions.map((r) => regionLabel(locale, r)).join(", ")}</p>
                </td>
                <td className="py-3 pr-4"><StageCell diffusion={c.diffusion} lifecycle={c.lifecycle} locale={locale} /></td>
                <td className="py-3 pr-4"><Trend card={c} locale={locale} /></td>
                <td className="py-3 pr-4 tabular-nums text-[13px] text-charcoal">{lastUsed(c) ? fmtDate(lastUsed(c)!) : "—"}</td>
                <td className="py-3 pr-4 text-[13px] text-charcoal">{where(c).length ? where(c).join(", ") : <span className="text-steel">—</span>}</td>
                <td className="py-3"><RiskCell item={c} locale={locale} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <ul className="divide-y divide-hairline border-b border-hairline md:hidden">
        {cards.map((c) => (
          <li key={c.term_id} className="py-3.5">
            <div className="flex items-start justify-between gap-3">
              <Link href={`/dictionary/${c.term_id}`} lang={langTag(c.lang)} className="min-w-0 text-[16px] font-semibold text-ink hover:underline">{c.canonical}</Link>
              <RiskCell item={c} locale={locale} />
            </div>
            <p className="mt-1 line-clamp-2 text-[14px] leading-[1.5] text-charcoal">{gloss(c, locale)}</p>
            <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[12px] text-steel">
              <StageCell diffusion={c.diffusion} lifecycle={c.lifecycle} locale={locale} />
              <span>{t(locale, "dash_mentions_4w")} <span className="tabular-nums text-ink">{fmtInt(c.mentions_4w)}</span></span>
              {lastUsed(c) && <span>{t(locale, "dash_last_used")} <span className="tabular-nums text-ink">{fmtDate(lastUsed(c)!)}</span></span>}
            </div>
          </li>
        ))}
      </ul>
    </>
  );
}
