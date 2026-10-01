import Link from "next/link";
import { regionName } from "@/components/graph-memes";
import { PageHeader } from "@/components/page-header";
import { PageShell } from "@/components/page-shell";
import { StatePanel } from "@/components/state-panel";
import { getGraphContents } from "@/lib/data";
import { t } from "@/lib/i18n";
import { langTag } from "@/lib/lang";
import { getLocale } from "@/lib/locale";

/* 콘텐츠 목록 — 콘텐츠를 고르면 그 작품에서 나라마다 나온 밈이 나온다. */
export default async function GraphIndexPage() {
  const [locale, list] = await Promise.all([getLocale(), getGraphContents()]);
  return (
    <PageShell>
      <div className="space-y-6">
        <PageHeader title={t(locale, "graph_title")} description={t(locale, "graph_intro")} />
        {list === null ? (
          <StatePanel role="alert" action={<Link href="/graph" className="text-[14px] text-link-blue hover:underline">{t(locale, "graph_retry")}</Link>}>{t(locale, "graph_err")}</StatePanel>
        ) : list.length === 0 ? (
          <StatePanel>{t(locale, "graph_none")}</StatePanel>
        ) : (
          <ul className="border-y border-hairline">
            {list.map((c) => {
              const names = Object.entries(c.labels).filter(([, v]) => v !== c.labels[locale]);
              return (
                <li key={c.key} className="border-t border-hairline py-3 first:border-t-0">
                  <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
                    <Link href={`/graph/${encodeURIComponent(c.key)}`} lang={langTag(c.labels[locale] ? locale : "en")} className="text-[16px] font-medium text-ink hover:underline">{c.labels[locale] ?? c.name}</Link>
                    <p className="text-[13px] tabular-nums text-steel">
                      {t(locale, "graph_memes").replace("{n}", String(c.memes))} · {c.regions.map((r) => regionName(locale, r)).join(" · ")}
                    </p>
                  </div>
                  <p className="mt-1 text-[13px] text-charcoal">
                    {names.map(([lang, v], i) => (
                      <span key={lang}>{i > 0 && " · "}<span lang={langTag(lang)}>{v}</span></span>
                    ))}
                  </p>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </PageShell>
  );
}
