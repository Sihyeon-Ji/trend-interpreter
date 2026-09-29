import Link from "next/link";
import { PageHeader } from "@/components/page-header";
import { PageShell } from "@/components/page-shell";
import { getMeta, getUpdates } from "@/lib/data";
import { t, type StringKey } from "@/lib/i18n";
import { fmtDateTime, regionLabel } from "@/lib/labels";
import { getLocale } from "@/lib/locale";

const ORDER = ["new_term", "verified", "meaning_changed", "spike", "reviewed", "recheck", "candidate_meaning"];

export default async function UpdatesPage() {
  const [locale, updates, meta] = await Promise.all([getLocale(), getUpdates(48), getMeta()]);
  const groups = ORDER.map((k) => [k, updates.filter((u) => u.kind === k)] as const).filter(([, l]) => l.length);
  return (
    <PageShell>
      <div className="space-y-8">
        <PageHeader title={t(locale, "updates_title")} description={t(locale, "updates_intro")}
          meta={meta?.last_run ? (
            <span className="flex flex-wrap gap-x-4">
              <span>{t(locale, "updates_last_run")} <span className="tabular-nums text-charcoal">{fmtDateTime(meta.last_run, locale)}</span></span>
              <span className="tabular-nums">{locale === "ko" ? `표현 ${meta.terms}개` : `${meta.terms} expressions`}</span>
            </span>
          ) : undefined} />
        {groups.length === 0 && <p className="rounded-lg border border-hairline px-4 py-8 text-center text-[14px] text-charcoal">{t(locale, "updates_none")}</p>}
        {groups.map(([kind, list]) => (
          <section key={kind}>
            <h2 className="text-[15px] font-semibold text-ink">{t(locale, `updates_kind_${kind}` as StringKey)} <span className="ml-1 text-[13px] font-normal text-steel">{list.length}</span></h2>
            <ul className="mt-2 divide-y divide-hairline border-y border-hairline text-[14px]">
              {list.slice(0, 30).map((u, i) => (
                <li key={i} className="grid grid-cols-[112px_minmax(0,1fr)] gap-3 py-2.5 sm:grid-cols-[150px_minmax(0,1fr)]">
                  <span className="text-steel tabular-nums">{fmtDateTime(u.at, locale)}</span>
                  <span className="text-ink">
                    {u.term_id ? <Link href={`/dictionary/${u.term_id}`} className="hover:underline">{u.label}</Link> : u.region ? <Link href={`/country/${u.region}`} className="hover:underline">{u.label}</Link> : u.label}
                    {u.region && <span className="ml-1.5 text-[12px] text-steel">{regionLabel(locale, u.region)}</span>}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </PageShell>
  );
}
