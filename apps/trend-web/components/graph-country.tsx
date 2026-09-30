import Link from "next/link";
import { t, type Locale } from "@/lib/i18n";
import { regionLabel } from "@/lib/labels";
import { langTag } from "@/lib/lang";
import type { GraphCountry, GraphItem } from "@/lib/types";

function Item({ item, locale, lang }: { item: GraphItem; locale: Locale; lang: string | undefined }) {
  const inDict = item.term_id && item.status === "verified";
  const external = (label: string) => (
    <a href={item.url} target="_blank" rel="noopener noreferrer" className="text-[13px] text-link-blue hover:underline">
      {label} <span aria-hidden>↗</span><span className="sr-only"> ({t(locale, "graph_external")})</span>
    </a>
  );
  return (
    <li className="space-y-0.5 border-t border-hairline py-2.5 first:border-t-0">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        {inDict ? (
          <Link href={`/dictionary/${encodeURIComponent(item.term_id!)}`} lang={lang} className="text-[15px] font-medium text-ink hover:underline">{item.title}</Link>
        ) : (
          <span lang={lang} className="text-[15px] text-ink">{item.title}</span>
        )}
        {item.status === "needs_review" && <span className="rounded-md border border-hairline-strong px-1.5 text-[12px] text-charcoal">{t(locale, "graph_checking")}</span>}
        {!inDict && item.url && external(t(locale, "graph_doc"))}
      </div>
      {inDict && item.definition && <p className="text-[14px] leading-[1.55] text-charcoal">{item.definition}</p>}
    </li>
  );
}

/** 나라 칸 하나 — 이름·그 나라의 콘텐츠 이름·모은 곳(작은 글씨)·항목 목록. 지도에서 누르면 #country-XX 로 오고 테두리가 짙어진다. */
export function GraphCountrySection({ country, locale, mine }: { country: GraphCountry; locale: Locale; mine: boolean }) {
  const lang = langTag(country.lang);
  const id = `country-${country.region}`;
  return (
    <section id={id} aria-labelledby={`${id}-h`} className="scroll-mt-6 space-y-3 rounded-lg border border-hairline px-5 py-4 target:border-ink target:border-2 target:px-[19px] target:py-[15px]">
      <header className="space-y-1">
        <h2 id={`${id}-h`} className="flex flex-wrap items-baseline gap-x-3 text-[18px] font-semibold text-ink">
          {regionLabel(locale, country.region)}
          {mine && <span className="rounded-md border border-hairline-strong px-1.5 text-[12px] font-normal text-charcoal">{t(locale, "graph_my_country")}</span>}
        </h2>
        <p className="text-[14px] text-charcoal">
          <span className="text-steel">{t(locale, "graph_local_name")} </span>
          <span lang={lang} className="font-medium text-ink">{country.label}</span>
        </p>
        {country.sources.length > 0 && (
          <p className="text-[12px] text-steel">{t(locale, "graph_sources")}: <span lang={lang}>{country.sources.join(" · ")}</span></p>
        )}
      </header>
      {country.items.length === 0 ? (
        <p className="text-[14px] text-steel">{t(locale, "graph_no_items")}</p>
      ) : (
        <ul>{country.items.map((it) => <Item key={`${it.title}-${it.url}`} item={it} locale={locale} lang={lang} />)}</ul>
      )}
    </section>
  );
}
