import Link from "next/link";
import { Sparkline } from "@/components/sparkline";
import { StatusBadge } from "@/components/status-badge";
import { t, type Locale } from "@/lib/i18n";
import { riskOf } from "@/lib/keyword";
import { L, fmtDate, fmtInt, regionLabel, sourceName } from "@/lib/labels";
import type { KeywordCard } from "@/lib/types";

const DIFF_TONE = { spreading: "good", underground: "good", mainstream: "neutral", fading: "muted" } as const;
// 표제어 원문의 말 — 화면 읽기 프로그램이 한글·가나·태국 글자를 제 발음으로 읽게 (docs/트렌드/디자인-개편.md 원칙 4)
const LANG_TAG: Record<string, string> = { zh: "zh-Hant", tl: "fil" };

function Stage({ card, locale }: { card: KeywordCard; locale: Locale }) {
  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
      {card.diffusion && <StatusBadge tone={DIFF_TONE[card.diffusion]}>{t(locale, `diffusion_${card.diffusion}`)}</StatusBadge>}
      <span className="text-[13px] text-charcoal">{L(locale).lifecycle[card.lifecycle]}</span>
    </div>
  );
}

function Risk({ card, locale }: { card: KeywordCard; locale: Locale }) {
  const r = riskOf(card);
  if (r) return <StatusBadge tone={r === "avoid" ? "avoid" : r === "caution" ? "caution" : "muted"}>{t(locale, `risk_${r}`)}</StatusBadge>;
  return <span className="text-[13px] text-steel">{card.risk_level === "none" ? t(locale, "risk_none_short") : "—"}</span>;
}

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
                  <Link href={`/dictionary/${c.term_id}`} lang={LANG_TAG[c.lang] ?? c.lang} className="text-[15px] font-semibold text-ink hover:underline">{c.canonical}</Link>
                  <p className="mt-0.5 truncate text-[13px] text-charcoal" title={gloss(c, locale)}>{gloss(c, locale)}</p>
                  <p className="mt-0.5 truncate text-[12px] text-steel">{c.regions.map((r) => regionLabel(locale, r)).join(", ")}</p>
                </td>
                <td className="py-3 pr-4"><Stage card={c} locale={locale} /></td>
                <td className="py-3 pr-4"><Trend card={c} locale={locale} /></td>
                <td className="py-3 pr-4 tabular-nums text-[13px] text-charcoal">{lastUsed(c) ? fmtDate(lastUsed(c)!) : "—"}</td>
                <td className="py-3 pr-4 text-[13px] text-charcoal">{where(c).length ? where(c).join(", ") : <span className="text-steel">—</span>}</td>
                <td className="py-3"><Risk card={c} locale={locale} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <ul className="divide-y divide-hairline border-b border-hairline md:hidden">
        {cards.map((c) => (
          <li key={c.term_id} className="py-3.5">
            <div className="flex items-start justify-between gap-3">
              <Link href={`/dictionary/${c.term_id}`} lang={LANG_TAG[c.lang] ?? c.lang} className="min-w-0 text-[16px] font-semibold text-ink hover:underline">{c.canonical}</Link>
              <Risk card={c} locale={locale} />
            </div>
            <p className="mt-1 line-clamp-2 text-[14px] leading-[1.5] text-charcoal">{gloss(c, locale)}</p>
            <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[12px] text-steel">
              <Stage card={c} locale={locale} />
              <span>{t(locale, "dash_mentions_4w")} <span className="tabular-nums text-ink">{fmtInt(c.mentions_4w)}</span></span>
              {lastUsed(c) && <span>{t(locale, "dash_last_used")} <span className="tabular-nums text-ink">{fmtDate(lastUsed(c)!)}</span></span>}
            </div>
          </li>
        ))}
      </ul>
    </>
  );
}
