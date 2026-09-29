import Link from "next/link";
import { notFound } from "next/navigation";
import { KeywordTable } from "@/components/keyword-table";
import { ListTabs } from "@/components/list-tabs";
import { PageHeader } from "@/components/page-header";
import { PageShell } from "@/components/page-shell";
import { StatePanel } from "@/components/state-panel";
import { TrendingSearchTable } from "@/components/trending-search-table";
import { buttonVariants } from "@/components/ui/button";
import { WhyList } from "@/components/why-list";
import { isCountryCode } from "@/lib/country";
import { getCountryPage } from "@/lib/data";
import { t } from "@/lib/i18n";
import { fmtDateTime, regionLabel } from "@/lib/labels";
import { getLocale } from "@/lib/locale";
import { TARGET_REGIONS } from "@/lib/reader";
import { cn } from "@/lib/utils";

/* 나라 화면 — 이 나라에서 지금 써도 되는 밈과 피할 밈, 이 나라 화제의 맥락. 탭 넷(지금 쓰이는 밈·주의가 필요한 밈·지금 뜨는 검색어·
   검색이 늘어난 이유)으로 나눠 한 화면에 쌓지 않는다(데스크톱 9,562px 였다). 밈 표는 대시보드와 같은 KeywordTable.
   목표 지역 밖(지도에서 들어오는 나라)은 검색어·이유만 보인다. 탭은 주소(?tab=)에만 둔다. */
const TABS = ["rising", "caution", "searches", "why"] as const;
type Tab = (typeof TABS)[number];
const MEMES_SHOWN = 20;

export default async function CountryPage({ params, searchParams }: {
  params: Promise<{ code: string }>; searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const [{ code }, sp, locale] = await Promise.all([params, searchParams, getLocale()]);
  const region = code.toUpperCase();
  if (!isCountryCode(region)) notFound();
  const target = TARGET_REGIONS.includes(region);
  const name = regionLabel(locale, region);
  const view = await getCountryPage(region);
  const self = `/country/${region}`;
  const link = "text-[14px] text-link-blue hover:underline";

  const header = (
    <PageHeader title={name} divider={false}
      crumbs={<><Link href="/map" className="hover:text-ink hover:underline">{t(locale, "nav_map")}</Link> › {name}</>}
      description={t(locale, target ? "country_intro" : "country_intro_other").replace("{country}", name)}
      meta={view?.updated_at ? <span>{t(locale, "dash_updated")} <span className="tabular-nums text-charcoal">{fmtDateTime(view.updated_at, locale)}</span></span> : undefined}
      actions={target ? (
        <>
          <Link href={`/?regions=${region}`} className={link}>{t(locale, "feeds_open_dashboard")}</Link>
          <Link href={`/recommend?regions=${region}`} className={cn(buttonVariants(), "h-10 w-full rounded-md px-4 text-[14px] sm:w-auto")}>
            {t(locale, "country_recommend").replace("{country}", name)}
          </Link>
        </>
      ) : undefined}>
      {!target && <p className="text-[13px] text-steel">{t(locale, "country_outside")}</p>}
    </PageHeader>
  );

  if (!view) {
    return (
      <PageShell>
        <div className="space-y-6">
          {header}
          <StatePanel role="alert" action={<Link href={self} className={link}>{t(locale, "feeds_retry")}</Link>}>{t(locale, "feeds_load_failed")}</StatePanel>
        </div>
      </PageShell>
    );
  }

  const board = view.board;
  const shown: Tab[] = board ? [...TABS] : ["searches", "why"];
  const tab: Tab = shown.includes(String(sp.tab) as Tab) ? (String(sp.tab) as Tab) : shown[0];
  const count: Record<Tab, number> = { rising: board?.rising.length ?? 0, caution: board?.caution.length ?? 0, searches: view.items.length, why: view.why.length };
  const label: Record<Tab, string> = { rising: t(locale, "dash_rising"), caution: t(locale, "dash_caution"), searches: t(locale, "country_trending"), why: t(locale, "country_why") };
  const tabs = shown.map((id) => ({ id, label: label[id], count: count[id], href: id === shown[0] ? self : `${self}?tab=${id}` }));
  const hasMeme = view.items.some((i) => i.category === "slang_meme" || i.category === "song_challenge");

  return (
    <PageShell>
      <div className="space-y-6">
        {header}
        <section aria-labelledby="country-list" className="space-y-3">
          <h2 id="country-list" className="sr-only">{label[tab]}</h2>
          <ListTabs items={tabs} current={tab} label={t(locale, "country_tabs")} />

          {(tab === "rising" || tab === "caution") && board && (() => {
            const cards = board[tab];
            if (!cards.length) {
              return tab === "rising"
                ? <StatePanel action={<Link href="/map" className={link}>{t(locale, "nav_map")}</Link>}>{t(locale, "country_none").replace("{country}", name)}</StatePanel>
                : <StatePanel>{t(locale, "dash_caution_empty")}</StatePanel>;
            }
            return (
              <>
                <p className="text-[13px] text-steel">{t(locale, `dash_${tab}_note`)}</p>
                <KeywordTable cards={cards.slice(0, MEMES_SHOWN)} locale={locale} linkRegions={[region]} />
                <div className="flex flex-col gap-1.5 pt-1">
                  {cards.length > MEMES_SHOWN && (
                    <Link href={`/?regions=${region}${tab === "caution" ? "&list=caution" : ""}`} className={link}>
                      {t(locale, "country_see_all").replace("{country}", name).replace("{n}", String(cards.length))}
                    </Link>
                  )}
                  {tab === "rising" && board.fading.length > 0 && (
                    <Link href={`/?regions=${region}&list=fading`} className={link}>{t(locale, "country_fading_link").replace("{n}", String(board.fading.length))}</Link>
                  )}
                </div>
              </>
            );
          })()}

          {tab === "searches" && (view.items.length === 0
            ? <StatePanel>{t(locale, "country_searches_empty")}</StatePanel>
            : (
              <>
                <p className="text-[13px] text-steel">{t(locale, "country_searches_note")}</p>
                {target && !hasMeme && <p className="text-[14px] text-charcoal">{t(locale, "country_searches_no_meme")}</p>}
                <TrendingSearchTable items={view.items} locale={locale} region={region} />
              </>
            ))}

          {tab === "why" && (
            <>
              <p className="text-[13px] text-steel">{t(locale, "country_why_note")}</p>
              {view.why.length ? <WhyList items={view.why} locale={locale} /> : <StatePanel>{t(locale, "country_why_empty")}</StatePanel>}
              {view.why_hidden > 0 && <p className="text-[13px] text-steel">{t(locale, "country_why_hidden").replace("{n}", String(view.why_hidden))}</p>}
            </>
          )}
        </section>
      </div>
    </PageShell>
  );
}
