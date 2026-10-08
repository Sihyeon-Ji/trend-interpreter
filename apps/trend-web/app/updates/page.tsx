import type { Metadata } from "next";
import Link from "next/link";
import { ChipMark } from "@/components/chip-mark";
import { ListTabs } from "@/components/list-tabs";
import { PageHeader } from "@/components/page-header";
import { PageShell } from "@/components/page-shell";
import { StatePanel } from "@/components/state-panel";
import { rowRegions, UpdatesTable } from "@/components/updates-table";
import { getUpdateFeed } from "@/lib/data";
import { t } from "@/lib/i18n";
import { fmtDateTime, regionLabel } from "@/lib/labels";
import { getLocale } from "@/lib/locale";
import { TARGET_REGIONS } from "@/lib/reader";
import { chipClass } from "@/lib/ui";

/* 최근 변화 — 이용자에게 보일 변화만: 새로 확인된 밈, 뜻이 바뀐 밈, 검색 급증. 다시 확인·뜻 제안·검수 결정 같은 작업 기록은
   관리 화면의 몫이다(백엔드 GET /updates?kinds=all). 종류와 지역은 주소(?kind=, ?regions=)에만 둔다. */
const KINDS = ["verified", "meaning_changed", "spike"] as const;
type Kind = (typeof KINDS)[number] | "all";

// 탭·화면 낭독기가 화면을 가를 수 있게 화면마다 제목을 둔다 — 여러 화면이 사이트 이름 하나뿐이었다(10-04)
export async function generateMetadata(): Promise<Metadata> {
  const locale = await getLocale();
  return { title: `${t(locale, "updates_title")} — ${t(locale, "site")}` };
}

export default async function UpdatesPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const [locale, sp, feed] = await Promise.all([getLocale(), searchParams, getUpdateFeed(48)]);
  const kind: Kind = KINDS.includes(String(sp.kind) as (typeof KINDS)[number]) ? (String(sp.kind) as Kind) : "all";
  const asked = [sp.regions].flat().filter(Boolean).join(",").split(",").map((s) => s.trim().toUpperCase());
  const regions = TARGET_REGIONS.filter((r) => asked.includes(r));
  const href = (next: { kind?: Kind; regions?: string[] }) => {
    const q = new URLSearchParams();
    const rs = next.regions ?? regions;
    const k = next.kind ?? kind;
    if (rs.length) q.set("regions", rs.join(","));
    if (k !== "all") q.set("kind", k);
    return q.size ? `/updates?${q}` : "/updates";
  };
  const header = (chips?: React.ReactNode) => (
    <PageHeader title={t(locale, "updates_title")} description={t(locale, "updates_intro")}
      meta={feed?.updated_at ? <span>{t(locale, "dash_updated")} <span className="tabular-nums text-charcoal">{fmtDateTime(feed.updated_at, locale)}</span></span> : undefined}
      actions={<Link href="/trends" className="text-[14px] text-link-blue hover:underline">{t(locale, "feeds_open_dashboard")}</Link>}>
      {chips}
    </PageHeader>
  );

  if (!feed) {
    return (
      <PageShell>
        <div className="space-y-6">
          {header()}
          <StatePanel role="alert" action={<Link href={href({})} className="text-[14px] text-link-blue hover:underline">{t(locale, "feeds_retry")}</Link>}>
            {t(locale, "feeds_load_failed")}
          </StatePanel>
        </div>
      </PageShell>
    );
  }

  const inRegion = regions.length ? feed.items.filter((r) => rowRegions(r).some((x) => regions.includes(x))) : feed.items;
  // 지역을 고르지 않았으면 서버가 자르기 전에 센 합계를, 골랐으면 받은 목록에서 센다
  const counts = regions.length ? Object.fromEntries(KINDS.map((k) => [k, inRegion.filter((r) => r.kind === k).length])) : feed.counts;
  const total = regions.length ? inRegion.length : feed.total;
  const rows = kind === "all" ? inRegion : inRegion.filter((r) => r.kind === kind);
  const tabs = [
    { id: "all", label: t(locale, "updates_all"), count: total, href: href({ kind: "all" }) },
    ...KINDS.map((k) => ({ id: k, label: t(locale, `updates_kind_${k}`), count: counts[k] ?? 0, href: href({ kind: k }) })),
  ];
  const perRegion = (r: string) => feed.items.filter((x) => rowRegions(x).includes(r)).length;
  const toggle = (r: string) => (regions.includes(r) ? regions.filter((x) => x !== r) : [...regions, r]);

  return (
    <PageShell>
      <div className="space-y-6">
        {header(
        <nav aria-label={t(locale, "dash_regions")} className="-mx-4 flex gap-1.5 overflow-x-auto px-4 [scrollbar-width:none] sm:mx-0 sm:flex-wrap sm:px-0">
          <Link href={href({ regions: [] })} className={chipClass(!regions.length)}>
            <ChipMark on={!regions.length} />{t(locale, "updates_regions_all")}{!regions.length && <span className="sr-only"> {t(locale, "chip_selected")}</span>}
          </Link>
          {TARGET_REGIONS.map((r) => {
            const on = regions.includes(r);
            return (
              <Link key={r} href={href({ regions: toggle(r) })} className={chipClass(on)}>
                <ChipMark on={on} />{regionLabel(locale, r)} <span className="tabular-nums opacity-75">{perRegion(r)}</span>
                {on && <span className="sr-only"> {t(locale, "chip_selected")}</span>}
              </Link>
            );
          })}
        </nav>)}
        <section aria-labelledby="updates-list" className="space-y-3">
          <h2 id="updates-list" className="sr-only">{tabs.find((x) => x.id === kind)?.label}</h2>
          <ListTabs items={tabs} current={kind} label={t(locale, "updates_kinds")} />
          {feed.total === 0 ? (
            <StatePanel action={<Link href="/trends" className="text-[14px] text-link-blue hover:underline">{t(locale, "feeds_open_dashboard")}</Link>}>{t(locale, "updates_none")}</StatePanel>
          ) : rows.length === 0 ? (
            <StatePanel action={<Link href="/updates" className="text-[14px] text-link-blue hover:underline">{t(locale, "updates_regions_all")}</Link>}>{t(locale, "updates_none_filtered")}</StatePanel>
          ) : (
            <UpdatesTable rows={rows} locale={locale} now={new Date().toISOString()} />
          )}
          {feed.total > feed.items.length && (
            <p className="text-[13px] text-steel">{t(locale, "updates_truncated").replace("{n}", String(feed.total)).replace("{m}", String(feed.items.length))}</p>
          )}
        </section>
      </div>
    </PageShell>
  );
}
