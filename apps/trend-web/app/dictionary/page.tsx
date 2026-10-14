import type { Metadata } from "next";
import Link from "next/link";
import { DictionaryList, type DictionaryState } from "@/components/dictionary-list";
import { PageHeader } from "@/components/page-header";
import { PageShell } from "@/components/page-shell";
import { StatePanel } from "@/components/state-panel";
import { packRows, toRow, type SortKey } from "@/lib/dictionary/rows";
import { getMeta, isSampleMode, loadTermRecords } from "@/lib/data";
import { t } from "@/lib/i18n";
import { fmtDateTime } from "@/lib/labels";
import { getLocale } from "@/lib/locale";
import { TARGET_REGIONS } from "@/lib/reader";
import { getReader } from "@/lib/reader-server";

type Search = { q?: string; regions?: string; kind?: string; lang?: string; risk?: string; sort?: string; page?: string };
const SORTS: SortKey[] = ["name", "used", "changed", "unfamiliar"];

// 탭·화면 낭독기가 화면을 가를 수 있게 화면마다 제목을 둔다 — 여러 화면이 사이트 이름 하나뿐이었다(10-04)
export async function generateMetadata(): Promise<Metadata> {
  const locale = await getLocale();
  return { title: `${t(locale, "dict_title")} — ${t(locale, "site")}` };
}

export default async function DictionaryPage({ searchParams }: { searchParams: Promise<Search> }) {
  const [{ records, ok }, locale, reader, meta, sp] = await Promise.all([loadTermRecords(true), getLocale(), getReader(), getMeta(), searchParams]);
  // 거르기·정렬 상태는 주소에 둔다 — 뒤로 가기·공유·대시보드에서 고른 지역(?regions=)을 이어받게
  const known = [...TARGET_REGIONS, "GLOBAL"];
  const initial: DictionaryState = {
    q: (sp.q ?? "").slice(0, 80),
    regions: (sp.regions ?? "").split(",").filter((r) => known.includes(r)),
    kind: sp.kind ?? "", lang: sp.lang ?? "", risk: sp.risk ?? "",
    // 기본은 최근 쓰인 순 — A→Z 첫 쪽이 'A Brony Tale'·'A Haunted House 2'(영화 소개뿐인 뜻)였다(10-14 점검)
    sort: SORTS.includes(sp.sort as SortKey) ? (sp.sort as SortKey) : "used",
    page: Math.max(1, Number.parseInt(sp.page ?? "1", 10) || 1),
  };
  const asOf = meta?.collected_at ?? meta?.last_run;
  const updated = !isSampleMode && asOf ? `${t(locale, "dash_updated")} ${fmtDateTime(asOf, locale)}` : null;
  return (
    <PageShell>
      <div className="space-y-6">
        <PageHeader title={t(locale, "dict_title")} description={t(locale, "dict_intro")}
          meta={updated && ok ? <span className="tabular-nums">{updated}</span> : undefined}
          actions={<Link href="/updates" className="text-[13px] text-link-blue hover:underline">{t(locale, "pg_dict_see_updates")}</Link>} />
        {!ok ? (
          <StatePanel role="alert" action={<a href={`/dictionary${Object.keys(sp).length ? `?${new URLSearchParams(sp as Record<string, string>)}` : ""}`} className="text-[14px] text-link-blue hover:underline">{t(locale, "pg_retry")}</a>}>
            {t(locale, "pg_load_failed")}
          </StatePanel>
        ) : records.length === 0 ? (
          <StatePanel action={<Link href="/trends" className="text-[14px] text-link-blue hover:underline">{t(locale, "pg_dict_go_dashboard")}</Link>}>
            {t(locale, "pg_dict_empty")}
          </StatePanel>
        ) : (
          <DictionaryList packed={packRows(records.map((r) => toRow(r, locale)))} locale={locale} readerGen={reader.gen ?? null} initial={initial} />
        )}
      </div>
    </PageShell>
  );
}
