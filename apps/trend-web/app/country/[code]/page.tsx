import Link from "next/link";
import { notFound } from "next/navigation";
import { PageHeader } from "@/components/page-header";
import { PageShell } from "@/components/page-shell";
import { WhyCard } from "@/components/why-card";
import { getCountryPage } from "@/lib/data";
import { t } from "@/lib/i18n";
import { L, fmtDateTime, regionLabel } from "@/lib/labels";
import { getLocale } from "@/lib/locale";
import { TARGET_REGIONS } from "@/lib/reader";
import { currentMeaning, textFor } from "@/lib/explain";
import { TREND_CATEGORIES } from "@/lib/trends/types";

export default async function CountryPage({ params }: { params: Promise<{ code: string }> }) {
  const { code } = await params;
  const region = code.toUpperCase();
  const locale = await getLocale();
  const labels = L(locale);
  if (!/^[A-Z]{2}$/.test(region)) notFound();
  const page = await getCountryPage(region);
  const gens = Object.entries(page.generation_share).sort((a, b) => b[1] - a[1]);
  return (
    <PageShell>
      <div className="space-y-10">
        <PageHeader title={regionLabel(locale, region)}
          crumbs={<><Link href="/map" className="hover:text-ink hover:underline">{t(locale, "nav_map")}</Link> › {regionLabel(locale, region)}</>}
          meta={page.updated_at ? <span>{t(locale, "updates_last_run")} <span className="tabular-nums text-charcoal">{fmtDateTime(page.updated_at, locale)}</span></span> : undefined}
          actions={TARGET_REGIONS.includes(region) ? <Link href={`/?regions=${region}`} className="text-[14px] text-link-blue hover:underline">{t(locale, "dash_open_country")}</Link> : undefined} />

        <section>
          <h2 className="text-[18px] font-semibold text-ink">{t(locale, "country_trending")}</h2>
          {page.items.length === 0 ? <p className="mt-2 text-[14px] text-steel">{t(locale, "country_none")}</p> : (
            <div className="mt-3 grid gap-x-8 gap-y-5 sm:grid-cols-2">
              {TREND_CATEGORIES.map((c) => {
                const list = page.items.filter((i) => i.category === c).sort((a, b) => a.rank - b.rank);
                if (!list.length) return null;
                return (
                  <div key={c}>
                    <h3 className="text-[12px] font-semibold text-steel">{labels.trendCategory[c]}</h3>
                    <ol className="mt-1 divide-y divide-hairline">
                      {list.map((i) => (
                        <li key={i.id} className="py-2">
                          <div className="flex items-baseline gap-2">
                            <span className="w-4 text-[12px] text-steel tabular-nums">{i.rank}</span>
                            <span className="text-[15px] font-medium text-ink">{i.term_id ? <Link href={`/dictionary/${i.term_id}`} className="hover:underline">{i.term}</Link> : i.term}</span>
                            <span className="ml-auto text-[12px] text-steel">{t(locale, `map_change_${i.change}` as const)}{i.gain_pct ? ` +${i.gain_pct.toLocaleString("en-US")}%` : ""}</span>
                          </div>
                          <p className="pl-6 text-[13px] text-charcoal">{i.note[locale]}</p>
                        </li>
                      ))}
                    </ol>
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {page.why.length > 0 && (
          <section>
            <h2 className="text-[18px] font-semibold text-ink">{t(locale, "why_title")}</h2>
            <div className="mt-2">{page.why.map((w) => <WhyCard key={w.term + w.date} w={w} locale={locale} />)}</div>
          </section>
        )}

        <section>
          <h2 className="text-[18px] font-semibold text-ink">{t(locale, "country_terms")} <span className="ml-1 text-[14px] font-normal text-steel">{page.terms.length}</span></h2>
          {page.terms.length === 0 ? <p className="mt-2 text-[14px] text-steel">{t(locale, "country_none")}</p> : (
            <ul className="mt-3 divide-y divide-hairline border-y border-hairline">
              {page.terms.map((r) => {
                const m = currentMeaning(r); const mt = textFor(r, locale);
                return (
                  <li key={r.term.term_id} className="grid gap-1 py-3 sm:grid-cols-[180px_1fr]">
                    <Link href={`/dictionary/${r.term.term_id}`} className="text-[15px] font-semibold text-ink hover:underline">{r.term.canonical}</Link>
                    <p className="text-[14px] text-charcoal">{mt?.definition ?? m?.definition ?? t(locale, "dict_pending")}</p>
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        {gens.length > 0 && (
          <section>
            <h2 className="text-[18px] font-semibold text-ink">{t(locale, "country_generation")}</h2>
            <ul className="mt-3 max-w-[480px] space-y-1.5">
              {gens.map(([g, v]) => (
                <li key={g} className="grid grid-cols-[72px_1fr_44px] items-center gap-3 text-[13px]">
                  <span className="text-charcoal">{labels.generation[g as keyof typeof labels.generation] ?? g}</span>
                  <span className="block h-[6px] rounded-[2px] bg-[#e6e8eb]"><span className="block h-full rounded-[2px] bg-[var(--ink)]" style={{ width: `${Math.round(v * 100)}%` }} /></span>
                  <span className="text-right text-steel tabular-nums">{Math.round(v * 100)}%</span>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </PageShell>
  );
}
