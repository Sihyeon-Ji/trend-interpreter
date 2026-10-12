import Link from "next/link";
import { StatusBadge, type Tone } from "@/components/status-badge";
import { koOrEn, t, type Locale } from "@/lib/i18n";
import { scriptLang } from "@/lib/lang";
import { L, fmtInt } from "@/lib/labels";
import { TREND_CATEGORIES, type Change, type TrendItem } from "@/lib/trends/types";

const CHANGE_TONE: Record<Change, Tone> = { up: "good", new: "neutral", flat: "muted", down: "muted" };

/** '무엇인가' — 화면 언어로 쓴 설명만. 기사 제목 원문이나 출처 이름('Google Trends now')이 설명 칸에 들어와 있었다(화면 개편 2차 검토). */
export function whatItIs(item: TrendItem, locale: Locale): string | null {
  const note = item.note[koOrEn(locale)]?.trim();   // 일본어 화면은 영어판
  if (!note || /^google trends\b/i.test(note)) return null;
  if (locale === "ko") return /[가-힣]/.test(note) ? note : null;
  return scriptLang(note) ? null : note;
}

export const sortSearches = (items: TrendItem[]) =>
  [...items].sort((a, b) => TREND_CATEGORIES.indexOf(a.category) - TREND_CATEGORIES.indexOf(b.category) || a.rank - b.rank);

function ChangeBadge({ item, locale }: { item: TrendItem; locale: Locale }) {
  return <StatusBadge tone={CHANGE_TONE[item.change]}>{t(locale, `map_change_${item.change}`)}</StatusBadge>;
}

const gain = (item: TrendItem) => (item.gain_pct ? `+${fmtInt(item.gain_pct)}%` : "—");

/* 나라 화면 '지금 뜨는 검색어'. 분야 순서 다음 순위 순으로 한 장의 표 — 두 칸 모자이크는 칸 높이가 들쭉날쭉하고 읽는 순서가 지그재그였다.
   사전에 있는 검색어만 링크다. 휴대폰은 한 줄 목록. */
export function TrendingSearchTable({ items, locale, region }: { items: TrendItem[]; locale: Locale; region: string }) {
  const labels = L(locale);
  const rows = sortSearches(items);
  const name = (i: TrendItem, cls: string) =>
    i.term_id ? <Link href={`/dictionary/${i.term_id}`} lang={scriptLang(i.term, region)} className={`${cls} hover:underline`}>{i.term}</Link>
      : <span lang={scriptLang(i.term, region)} className={cls}>{i.term}</span>;
  return (
    <>
      <div className="hidden overflow-x-auto md:block">
        <table className="w-full min-w-[880px] border-collapse text-left">
          <caption className="sr-only">{t(locale, "country_searches_caption")}</caption>
          <thead>
            <tr className="border-b border-hairline text-[13px] text-steel">
              <th scope="col" className="w-[130px] py-2.5 pr-4 font-medium">{t(locale, "country_col_category")}</th>
              <th scope="col" className="w-[56px] py-2.5 pr-4 text-right font-medium">{t(locale, "country_col_rank")}</th>
              <th scope="col" className="w-[240px] py-2.5 pr-4 font-medium">{t(locale, "country_col_query")}</th>
              <th scope="col" className="py-2.5 pr-4 font-medium">{t(locale, "country_col_what")}</th>
              <th scope="col" className="w-[110px] py-2.5 pr-4 font-medium">{t(locale, "country_col_change")}</th>
              <th scope="col" className="w-[110px] py-2.5 text-right font-medium">{t(locale, "country_col_gain")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((i) => {
              const what = whatItIs(i, locale);
              return (
                <tr key={i.id} className={`border-b border-hairline align-top${i.term_id ? " hover:bg-surface-soft" : ""}`}>
                  <td className="py-3 pr-4 text-[13px] text-charcoal">{labels.trendCategory[i.category]}</td>
                  <td className="py-3 pr-4 text-right tabular-nums text-[14px] text-charcoal">{i.rank}</td>
                  <td className="py-3 pr-4">{name(i, "text-[15px] font-semibold text-ink")}</td>
                  <td className="max-w-0 py-3 pr-4 text-[14px] text-charcoal">
                    {what ? <p className="truncate" title={what}>{what}</p> : <span className="text-steel">—</span>}
                  </td>
                  <td className="py-3 pr-4"><ChangeBadge item={i} locale={locale} /></td>
                  <td className="py-3 text-right tabular-nums text-[14px] text-ink">{gain(i)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <ul className="divide-y divide-hairline border-b border-hairline md:hidden">
        {rows.map((i) => {
          const what = whatItIs(i, locale);
          return (
            <li key={i.id} className="py-3.5">
              <div className="flex items-start justify-between gap-3">
                {name(i, "min-w-0 text-[16px] font-semibold text-ink")}
                <ChangeBadge item={i} locale={locale} />
              </div>
              {what && <p className="mt-1 line-clamp-2 text-[14px] leading-[1.5] text-charcoal">{what}</p>}
              <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-steel">
                <span>{t(locale, "country_col_category")} <span className="text-ink">{labels.trendCategory[i.category]}</span></span>
                <span>{t(locale, "country_col_rank")} <span className="tabular-nums text-ink">{i.rank}</span></span>
                {i.gain_pct ? <span>{t(locale, "country_col_gain")} <span className="tabular-nums text-ink">{gain(i)}</span></span> : null}
              </div>
            </li>
          );
        })}
      </ul>
    </>
  );
}
