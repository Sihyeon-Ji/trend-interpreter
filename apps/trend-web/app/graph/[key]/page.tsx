import Link from "next/link";
import { notFound } from "next/navigation";
import { GraphCountrySection } from "@/components/graph-country";
import { GraphMap } from "@/components/graph-map";
import { PageHeader } from "@/components/page-header";
import { PageShell } from "@/components/page-shell";
import { getGraphContent } from "@/lib/data";
import { t } from "@/lib/i18n";
import { fmtDateTime } from "@/lib/labels";
import { langTag } from "@/lib/lang";
import { getLocale } from "@/lib/locale";
import { getReader } from "@/lib/reader-server";

/* 콘텐츠 → 나라별 파생 항목. 머리(이름들) → 연결 그림 → 나라별 칸. 로그인한 사람의 나라가 있으면 그 칸을 맨 앞에. */
export default async function GraphContentPage({ params }: { params: Promise<{ key: string }> }) {
  const { key } = await params;
  const [locale, data, reader] = await Promise.all([getLocale(), getGraphContent(decodeURIComponent(key)), getReader()]);
  if (!data) notFound();
  const { content } = data;
  const title = content.labels[locale] ?? content.name;
  const countries = [...data.countries].sort((a, b) => Number(b.region === reader.region) - Number(a.region === reader.region));
  const others = Object.entries(content.labels).filter(([, v]) => v !== title);
  return (
    <PageShell>
      <div className="space-y-8">
        <PageHeader crumbs={<Link href="/graph" className="hover:text-ink hover:underline">{t(locale, "graph_back")}</Link>}
          title={title}
          meta={data.updated_at ? <span>{t(locale, "dash_updated")} <span className="tabular-nums text-charcoal">{fmtDateTime(data.updated_at, locale)}</span></span> : undefined}
          description={<>
            <span className="sr-only">{t(locale, "graph_names")}: </span>
            {others.map(([lang, v], i) => <span key={lang}>{i > 0 && " · "}<span lang={langTag(lang)}>{v}</span></span>)}
          </>} />
        {data.preview && <p className="border-l border-ink pl-3 text-[13px] text-steel">{t(locale, "graph_preview")}</p>}
        <GraphMap name={title} countries={countries} locale={locale} />
        <div className="space-y-4">
          {countries.map((c) => <GraphCountrySection key={c.region} country={c} locale={locale} mine={c.region === reader.region} />)}
        </div>
      </div>
    </PageShell>
  );
}
