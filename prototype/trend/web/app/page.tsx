import { TrendExplorer } from "@/components/trend-explorer";
import { TrendMatrix } from "@/components/trend-matrix";
import { getMeta, getTrendBoard, getUpdates } from "@/lib/data";
import { t } from "@/lib/i18n";
import { getLocale } from "@/lib/locale";
import { getReader } from "@/lib/reader-server";

export default async function HomeMap({ searchParams }: { searchParams: Promise<{ region?: string; topic?: string }> }) {
  const locale = await getLocale();
  const [board, meta, updates] = await Promise.all([getTrendBoard(), getMeta(), getUpdates(24)]);
  const sp = await searchParams;
  const reader = await getReader();
  const wanted = sp.region ?? reader.region;
  const region = wanted && board.items.some((i) => i.region === wanted) ? wanted : null;
  const topic = sp.topic && board.topics.some((x) => x.id === sp.topic) ? sp.topic : null;
  return (
    <main className="flex-1">
      <TrendExplorer board={board} locale={locale} initialRegion={region} initialTopic={topic} meta={meta} updatesCount={updates.length} />
      <div className="mx-auto w-full max-w-[1120px] px-4 pb-12 sm:px-6">
        <TrendMatrix board={board} locale={locale} />
        <p className="mt-6 text-[13px] text-steel">{t(locale, "map_source")}</p>
      </div>
    </main>
  );
}
