import Link from "next/link";
import { t, type Locale } from "@/lib/i18n";
import { L, regionLabel } from "@/lib/labels";
import { TREND_CATEGORIES, type TrendBoard } from "@/lib/trends/types";

export function TrendMatrix({ board, locale }: { board: TrendBoard; locale: Locale }) {
  const labels = L(locale);
  const regions = [...new Set(board.items.map((i) => i.region))].sort((a, b) => regionLabel(locale, a).localeCompare(regionLabel(locale, b), locale));
  return (
    <section className="mt-10">
      <h2 className="text-[18px] font-semibold text-ink">{t(locale, "map_table_title")}</h2>
      <p className="mt-1 text-[13px] text-steel">{t(locale, "map_table_hint")}</p>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full min-w-[880px] border-collapse text-[13px]">
          <thead>
            <tr className="border-b border-hairline text-left text-steel">
              <th className="py-2 pr-3 font-medium">{t(locale, "map_country")}</th>
              {TREND_CATEGORIES.map((c) => <th key={c} className="py-2 pr-3 font-medium">{labels.trendCategory[c]}</th>)}
            </tr>
          </thead>
          <tbody>
            {regions.map((r) => (
              <tr key={r} className="border-b border-hairline align-top">
                <th scope="row" className="py-2.5 pr-3 text-left font-medium text-ink whitespace-nowrap">{regionLabel(locale, r)}</th>
                {TREND_CATEGORIES.map((c) => {
                  const cell = board.items.filter((i) => i.region === r && i.category === c).sort((a, b) => a.rank - b.rank);
                  const top = cell[0];
                  return (
                    <td key={c} className="py-2.5 pr-3 text-charcoal">
                      {top ? (
                        <>
                          {top.term_id ? <Link href={`/dictionary/${top.term_id}`} className="text-ink hover:underline">{top.term}</Link> : <span className="text-ink">{top.term}</span>}
                          {cell.length > 1 && <span className="ml-1 text-steel">+{cell.length - 1}</span>}
                        </>
                      ) : (
                        <span className="text-hairline-strong">—</span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
