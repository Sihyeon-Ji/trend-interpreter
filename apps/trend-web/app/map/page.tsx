import { TrendExplorer } from "@/components/trend-explorer";
import { TrendMatrix } from "@/components/trend-matrix";
import { getMeta, getTrendBoard, getUpdates } from "@/lib/data";
import { t } from "@/lib/i18n";
import { getLocale } from "@/lib/locale";
import { getReader } from "@/lib/reader-server";

/* 세계 지도 — 나라를 건너간 트렌드와 나라별 차이. 대시보드의 지역을 고르는 화면이기도 하다(ADR 0001, docs/트렌드/디자인-개편.md). */
export default async function WorldMap({ searchParams }: { searchParams: Promise<{ region?: string; topic?: string }> }) {
  const locale = await getLocale();
  const [board, meta, updates] = await Promise.all([getTrendBoard(), getMeta(), getUpdates(24)]);
  const sp = await searchParams;
  const reader = await getReader();
  const wanted = sp.region ?? reader.region;
  const region = wanted && board.items.some((i) => i.region === wanted) ? wanted : null;
  const topic = sp.topic && board.topics.some((x) => x.id === sp.topic) ? sp.topic : null;
  return (
    <main id="main" className="flex-1">
      <TrendExplorer board={board} locale={locale} initialRegion={region} initialTopic={topic} meta={meta} updatesCount={updates.length} />
      <div className="w-full max-w-[1200px] px-4 pb-12 sm:px-6 lg:px-8">
        <TrendMatrix board={board} locale={locale} />
        <p className="mt-6 text-[13px] text-steel">{t(locale, "map_source")}</p>
      </div>
    </main>
  );
}
