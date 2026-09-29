import type { Metadata } from "next";
import { PageShell } from "@/components/page-shell";
import { TrendExplorer } from "@/components/trend-explorer";
import { getMapData } from "@/lib/data";
import { t } from "@/lib/i18n";
import { getLocale } from "@/lib/locale";

export async function generateMetadata(): Promise<Metadata> {
  const locale = await getLocale();
  return { title: `${t(locale, "mp_title")} — ${t(locale, "site")}` };
}

/* 세계 지도 — 대시보드의 지역을 고르는 화면이자, 나라를 건너간 밈이 나라마다 어떻게 다른지 보는 곳(ADR 0001, docs/트렌드/디자인-개편.md).
   고른 지역·탭·밈은 주소(?regions=·?tab=·?topic=)에만 두고 화면(TrendExplorer)이 읽는다. 서버가 실패하면 error.tsx. */
export default async function WorldMap() {
  const [locale, { keywords, board }] = await Promise.all([getLocale(), getMapData()]);
  return (
    <PageShell>
      <TrendExplorer keywords={keywords} board={board} locale={locale} />
    </PageShell>
  );
}
