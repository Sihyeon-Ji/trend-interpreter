import Link from "next/link";
import { t, text2, type Locale } from "@/lib/i18n";
import { whyAnchor } from "@/lib/country";
import { scriptLang } from "@/lib/lang";
import { L, fmtDate, sourceName } from "@/lib/labels";
import type { TrendWhy } from "@/lib/trends/types";

const ACTORS_SHOWN = 3;

/** 화면 언어와 다른 글자로 쓴 글에만 lang 을 단다 */
const otherLang = (text: string, locale: Locale, region?: string) => {
  const l = scriptLang(text, region);
  return l && l !== locale ? l : undefined;
};

/* 나라 화면 '검색이 늘어난 이유'. 검색어 하나에 한 행: 이유 한 문장, 라벨 칸(계기·관련 인물·첫 신호), 글자 토글로 여는 근거 표.
   가운뎃점으로 사실을 잇지 않는다(docs/트렌드/디자인-개편.md 원칙 6). 행 id 는 최근 변화의 검색 급증 행이 가리킨다. */
export function WhyList({ items, locale }: { items: TrendWhy[]; locale: Locale }) {
  const labels = L(locale);
  return (
    <ol className="divide-y divide-hairline border-y border-hairline">
      {items.map((w) => {
        const actors = w.actors.map((a) => a.name);
        const more = actors.length - ACTORS_SHOWN;
        const why = text2(w.why_now, locale);
        return (
          <li key={w.term + w.date} id={whyAnchor(w.term)} className="scroll-mt-20 py-4 target:bg-surface-soft">
            <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
              <h3 lang={otherLang(w.term, locale, w.region)} className="min-w-0 text-[15px] font-semibold text-ink">{w.term}</h3>
              <time dateTime={String(w.date)} className="text-[13px] tabular-nums text-steel">{fmtDate(String(w.date))}</time>
            </div>
            {/* 일본어판이 없는 옛 이유는 일본어 화면에 영어판 */}
            <p lang={otherLang(why, locale, w.region) ?? (locale === "ja" && !w.why_now.ja ? "en" : undefined)} className="mt-1 max-w-[720px] text-[14px] leading-[1.55] text-charcoal">{why}</p>
            <dl className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-[13px]">
              <div className="flex gap-1.5"><dt className="text-steel">{t(locale, "country_why_trigger")}</dt><dd className="text-charcoal">{labels.trigger[w.trigger] ?? w.trigger}</dd></div>
              {actors.length > 0 && (
                <div className="flex min-w-0 gap-1.5">
                  <dt className="shrink-0 text-steel">{t(locale, "why_actors")}</dt>
                  <dd className="min-w-0 text-charcoal">
                    {actors.slice(0, ACTORS_SHOWN).map((a, i) => <span key={a}>{i > 0 && ", "}<span lang={otherLang(a, locale, w.region)}>{a}</span></span>)}
                    {more > 0 && <span className="text-steel"> {t(locale, "country_why_more").replace("{n}", String(more))}</span>}
                  </dd>
                </div>
              )}
              {w.first_signal && <div className="flex gap-1.5"><dt className="text-steel">{t(locale, "why_first_signal")}</dt><dd className="tabular-nums text-charcoal">{fmtDate(w.first_signal)}</dd></div>}
            </dl>
            {w.evidence.length > 0 && (
              <details className="group mt-2">
                <summary className="inline-block cursor-pointer list-none text-[13px] text-link-blue hover:underline [&::-webkit-details-marker]:hidden">
                  <span className="group-open:hidden">{t(locale, "country_why_show").replace("{n}", String(w.evidence.length))}</span>
                  <span className="hidden group-open:inline">{t(locale, "country_why_hide")}</span>
                </summary>
                <div className="mt-2 overflow-x-auto">
                  <table className="w-full min-w-[560px] border-collapse text-left text-[13px]">
                    <thead>
                      <tr className="border-b border-hairline text-steel">
                        <th scope="col" className="w-[88px] py-1.5 pr-3 font-medium">{t(locale, "country_ev_kind")}</th>
                        <th scope="col" className="w-[140px] py-1.5 pr-3 font-medium">{t(locale, "country_ev_source")}</th>
                        <th scope="col" className="w-[96px] py-1.5 pr-3 font-medium">{t(locale, "country_ev_date")}</th>
                        <th scope="col" className="py-1.5 font-medium">{t(locale, "country_ev_title")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {w.evidence.map((e) => (
                        <tr key={e.url} className="border-b border-hairline align-top">
                          <td className="py-1.5 pr-3 text-charcoal">{labels.evidenceKind[e.kind as keyof typeof labels.evidenceKind] ?? e.kind}</td>
                          <td className="py-1.5 pr-3 text-charcoal">{sourceName(locale, e.source_domain)}</td>
                          <td className="py-1.5 pr-3 tabular-nums text-charcoal">{fmtDate(e.observed_at)}</td>
                          <td className="max-w-0 py-1.5">
                            <Link href={e.url} target="_blank" rel="noreferrer" lang={otherLang(e.title, locale, w.region)} className="block truncate text-link-blue hover:underline" title={e.title}>
                              {e.title}<span className="sr-only"> {t(locale, "feeds_new_window")}</span>
                            </Link>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
            )}
          </li>
        );
      })}
    </ol>
  );
}
