import Link from "next/link";
import { notFound } from "next/navigation";
import { CrossTable, RegionList, regionName } from "@/components/graph-memes";
import { PageHeader } from "@/components/page-header";
import { PageShell } from "@/components/page-shell";
import { getGraphContent } from "@/lib/data";
import { t } from "@/lib/i18n";
import { fmtDateTime } from "@/lib/labels";
import { langTag } from "@/lib/lang";
import { getLocale } from "@/lib/locale";
import { getReader } from "@/lib/reader-server";
import type { GraphVariant } from "@/lib/types";

/* 콘텐츠 하나 → 나라를 건너간 밈(관계표) → 나라별 밈. 로그인한 사람의 나라가 있으면 그 나라 칸을 맨 앞에. */
export default async function GraphContentPage({ params }: { params: Promise<{ key: string }> }) {
  const { key } = await params;
  const [locale, data, reader] = await Promise.all([getLocale(), getGraphContent(decodeURIComponent(key)), getReader()]);
  if (!data) notFound();
  const { content } = data;
  const title = content.labels[locale] ?? content.name;
  const others = Object.entries(content.labels).filter(([, v]) => v !== title);
  const cross = data.memes.filter((m) => new Set(m.variants.map((v) => v.region)).size > 1);
  const crossRegions = data.regions.filter((r) => cross.some((m) => m.variants.some((v) => v.region === r)));
  const single = new Map<string, GraphVariant[]>();
  for (const m of data.memes) {
    if (cross.includes(m)) continue;
    for (const v of m.variants) single.set(v.region, [...(single.get(v.region) ?? []), v]);
  }
  const regions = [...single.keys()].sort((a, b) => Number(b === reader.region) - Number(a === reader.region));
  return (
    <PageShell>
      <div className="space-y-10">
        <PageHeader crumbs={<Link href="/graph" className="hover:text-ink hover:underline">{t(locale, "graph_back")}</Link>}
          title={title}
          meta={data.updated_at ? <span>{t(locale, "dash_updated")} <span className="tabular-nums text-charcoal">{fmtDateTime(data.updated_at, locale)}</span></span> : undefined}
          description={<>
            <span className="sr-only">{t(locale, "graph_names")}: </span>
            {others.map(([lang, v], i) => <span key={lang}>{i > 0 && " · "}<span lang={langTag(lang)}>{v}</span></span>)}
          </>} />
        {data.preview && <p className="border-l border-ink pl-3 text-[13px] text-steel">{t(locale, "graph_preview")}</p>}
        {cross.length > 0 && (
          <section aria-labelledby="cross-h" className="space-y-2">
            <h2 id="cross-h" className="text-[18px] font-semibold text-ink">{t(locale, "graph_cross")}</h2>
            <p className="text-[13px] text-steel">{t(locale, "graph_cross_hint")}</p>
            <CrossTable memes={cross} regions={crossRegions} locale={locale} />
          </section>
        )}
        {regions.length > 1 && (
          <nav aria-label={t(locale, "graph_jump")} className="flex flex-wrap gap-x-4 gap-y-1 text-[14px]">
            {regions.map((r) => (
              <a key={r} href={`#region-${r}`} className="text-link-blue hover:underline">
                {regionName(locale, r)} <span className="tabular-nums text-steel">{single.get(r)!.length}</span>
              </a>
            ))}
          </nav>
        )}
        {regions.map((r) => <RegionList key={r} region={r} memes={single.get(r)!} locale={locale} mine={r === reader.region} />)}
      </div>
    </PageShell>
  );
}
