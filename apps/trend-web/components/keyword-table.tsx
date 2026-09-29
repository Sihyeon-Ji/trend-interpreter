import Link from "next/link";
import { Sparkline } from "@/components/sparkline";
import { RiskCell, StageCell } from "@/components/term-status";
import { t, type Locale } from "@/lib/i18n";
import { langTag } from "@/lib/lang";
import { fmtDate, fmtInt, regionLabel, sourceName } from "@/lib/labels";
import type { KeywordCard } from "@/lib/types";
import { cn } from "@/lib/utils";

const lastUsed = (c: KeywordCard) => c.last_used ?? c.last_seen ?? null;
const gloss = (c: KeywordCard, locale: Locale) => (locale === "ko" ? c.gloss_ko : c.gloss_en);
const quiet = (c: KeywordCard) => !c.weekly.some((p) => p.count);   // 12주 동안 언급이 없다 — '0' 대신 '—'

// 행 전체가 사전 항목 링크 하나다(탭 멈춤도 하나): 표제어 링크의 ::after 가 행을 덮고, 초점은 그 ::after 에 파랑 테두리로 보인다
const rowLink = "after:absolute after:inset-0 focus-visible:outline-none focus-visible:after:outline-2 focus-visible:after:-outline-offset-2 focus-visible:after:outline-link-blue";

function Mentions({ card }: { card: KeywordCard }) {
  if (quiet(card)) return <span className="text-[14px] text-steel">—</span>;
  return (
    <span className="inline-flex items-center justify-end gap-3">
      {/* 같은 칸의 숫자와 열 머리가 뜻을 전한다 — 그림은 읽지 않는다. 1280px 미만에서는 숫자만 */}
      <span aria-hidden className="hidden xl:inline-flex"><Sparkline points={card.weekly} width={72} height={20} /></span>
      <span className="tabular-nums text-[14px] text-ink">{fmtInt(card.mentions_4w)}</span>
    </span>
  );
}

/* 대시보드 목록. 1024px 이상은 표, 그 아래는 선으로만 나눈 목록 행 — 카드 모자이크를 쓰지 않는다. 행을 누르면 사전 항목(뜻·근거·신호).
   표는 최소 폭·가로 스크롤 없이 칸 우선순위로 줄인다: 1280px 미만에서는 '주로 보인 곳' 칸과 스파크라인을 숨긴다.
   showRegions: 전체·글로벌을 볼 때만 표현 아래에 쓰이는 나라를 쓴다(한 나라를 보면 모든 행이 같은 나라라 뺀다). */
export function KeywordTable({ cards, locale, showRegions = false }: { cards: KeywordCard[]; locale: Locale; showRegions?: boolean }) {
  const where = (c: KeywordCard) => c.communities.slice(0, 2).map((s) => sourceName(locale, s.domain));
  const regions = (c: KeywordCard) => (showRegions && c.regions.length
    ? <p className="mt-0.5 text-[12px] text-steel">{c.regions.map((r) => (r === "GLOBAL" ? t(locale, "dash_global") : regionLabel(locale, r))).join(", ")}</p> : null);
  const th = "sticky top-0 z-10 border-b border-hairline bg-surface py-2.5 pr-4 text-[13px] font-medium text-steel";
  return (
    <>
      <table className="hidden w-full table-fixed border-collapse text-left lg:table">
        <caption className="sr-only">{t(locale, "dash_table_caption")}</caption>
        <thead>
          <tr>
            <th scope="col" className={cn(th, "pl-3")}>{t(locale, "dash_col_keyword")}</th>
            <th scope="col" className={cn(th, "w-[150px]")}>{t(locale, "dash_col_stage")}</th>
            <th scope="col" className={cn(th, "w-[104px] text-right xl:w-[176px]")}>{t(locale, "dash_mentions_4w")}</th>
            <th scope="col" className={cn(th, "w-[108px] text-right")}>{t(locale, "dash_last_used")}</th>
            <th scope="col" className={cn(th, "hidden w-[150px] xl:table-cell")}>{t(locale, "dash_seen_on")}</th>
            <th scope="col" className={cn(th, "w-[124px]")}>{t(locale, "dash_col_risk")}</th>
          </tr>
        </thead>
        <tbody>
          {cards.map((c) => (
            <tr key={c.term_id} className="relative border-b border-hairline align-top hover:bg-surface-soft">
              <td className="py-3 pr-4 pl-3">
                <Link href={`/dictionary/${c.term_id}`} lang={langTag(c.lang)} className={cn("text-[15px] font-semibold text-ink", rowLink)}>{c.canonical}</Link>
                <p className="mt-0.5 truncate text-[13px] text-charcoal" title={gloss(c, locale)}>{gloss(c, locale)}</p>
                {regions(c)}
              </td>
              <td className="py-3 pr-4"><StageCell diffusion={c.diffusion} lifecycle={c.lifecycle} locale={locale} /></td>
              <td className="py-3 pr-4 text-right"><Mentions card={c} /></td>
              <td className="py-3 pr-4 text-right tabular-nums text-[13px] text-charcoal">{fmtDate(lastUsed(c))}</td>
              <td className="hidden py-3 pr-4 text-[13px] text-charcoal xl:table-cell">{where(c).length ? where(c).join(", ") : <span className="text-steel">—</span>}</td>
              <td className="py-3"><RiskCell item={c} locale={locale} /></td>
            </tr>
          ))}
        </tbody>
      </table>

      <ul className="divide-y divide-hairline border-y border-hairline lg:hidden">
        {cards.map((c) => (
          <li key={c.term_id} className="relative py-3.5 hover:bg-surface-soft">
            <div className="flex items-start justify-between gap-3">
              <Link href={`/dictionary/${c.term_id}`} lang={langTag(c.lang)} className={cn("min-w-0 text-[16px] font-semibold text-ink", rowLink)}>{c.canonical}</Link>
              {/* 휴대폰에서는 '특이 사항 없음' 만 생략한다 — 주의·사용 자제·판단 보류·확인 전은 그대로 */}
              {c.risk_level !== "none" && <RiskCell item={c} locale={locale} />}
            </div>
            <p className="mt-1 truncate text-[14px] text-charcoal">{gloss(c, locale)}</p>
            {regions(c)}
            <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-[12px] text-steel">
              <StageCell diffusion={c.diffusion} lifecycle={c.lifecycle} locale={locale} />
              {lastUsed(c) && <span>{t(locale, "dash_last_used")} <span className="tabular-nums text-charcoal">{fmtDate(lastUsed(c))}</span></span>}
            </div>
          </li>
        ))}
      </ul>
    </>
  );
}

/** 쪽 넘김 — '41개 중 1–30' 과 이전·다음. 한 쪽뿐이면 건수 문장만. 더 갈 쪽이 없으면 누를 수 없게(aria-disabled) 회색으로. */
export function KeywordPager({ total, page, size, href, locale }: { total: number; page: number; size: number; href: (page: number) => string; locale: Locale }) {
  const pages = Math.max(1, Math.ceil(total / size));
  const range = t(locale, "dash_page_range").replace("{total}", fmtInt(total))
    .replace("{from}", fmtInt((page - 1) * size + 1)).replace("{to}", fmtInt(Math.min(total, page * size)));
  const btn = "inline-flex h-11 items-center rounded-md border px-3.5 text-[14px] lg:h-9";
  const step = (to: number, label: string) => (to >= 1 && to <= pages
    ? <Link href={href(to)} className={cn(btn, "border-hairline-strong text-ink hover:border-ink")}>{label}</Link>
    : <span aria-disabled="true" className={cn(btn, "border-hairline text-steel")}>{label}</span>);
  return (
    <div className="flex items-center justify-between gap-4">
      <p className="tabular-nums text-[13px] text-steel">{range}</p>
      {pages > 1 && (
        <nav aria-label={t(locale, "dash_pages")} className="flex gap-2">
          {step(page - 1, t(locale, "dash_prev"))}
          {step(page + 1, t(locale, "dash_next"))}
        </nav>
      )}
    </div>
  );
}
