import Link from "next/link";
import type { Metadata } from "next";
import { RegionPicker } from "@/components/lab/f-report/region-picker";
import { ReportBoard } from "@/components/lab/f-report/report-board";
import { SinceVisit, type UpdateLite } from "@/components/lab/f-report/since-visit";
import { Spotlight } from "@/components/lab/f-report/spotlight";
import { Watchlist } from "@/components/lab/f-report/watchlist";
import { getGenerationCurves, getKeywordBoard, getUpdates } from "@/lib/data";
import { c, REGIONS, regionSentence } from "@/lib/lab/f-report-copy";
import { combineCurves, filterRows, newlyVerified, pickSpotlight, toRow, type Row, type Trend } from "@/lib/lab/f-report";
import { fmtDateTime } from "@/lib/labels";
import { getLocale } from "@/lib/locale";
import type { KeywordCard, KeywordList } from "@/lib/types";

type Search = { regions?: string | string[]; page?: string; q?: string; list?: string };

function parse(sp: Search) {
  const regions = [sp.regions].flat().filter(Boolean).join(",").split(",").map((s) => s.trim().toUpperCase()).filter((r) => REGIONS.includes(r));
  const page = Math.max(1, Number.parseInt(sp.page ?? "1", 10) || 1);
  const q = (sp.q ?? "").trim().slice(0, 60);
  const list: KeywordList = sp.list === "fading" || sp.list === "caution" ? sp.list : "rising";
  return { regions: [...new Set(regions)], page, q, list };
}

export async function generateMetadata({ searchParams }: { searchParams: Promise<Search> }): Promise<Metadata> {
  const [locale, sp] = await Promise.all([getLocale(), searchParams]);
  const { regions } = parse(sp);
  const where = regionSentence(locale, regions);
  return { title: locale === "ko" ? `지금 ${where}에서 쓰이는 밈 · 트렌드 통역` : `Memes in use now in ${where} · Trend Interpreter` };
}

/** 리포트 홈. 지역이 머리이고, 목록은 대시보드(규칙이 매긴 순서), 추이는 네이버 데이터랩 나이대 곡선에서만 계산한다. */
export default async function FReportHome({ searchParams }: { searchParams: Promise<Search> }) {
  const [locale, sp] = await Promise.all([getLocale(), searchParams]);
  const { regions, page, q, list } = parse(sp);
  const [board, updates] = await Promise.all([getKeywordBoard(regions, page), getUpdates(168)]);

  // 세 목록의 카드를 한 번씩만 — 주의 밈은 쓰이는·식는 목록에도 있다
  const cards = new Map<string, KeywordCard>();
  for (const cd of [...board.rising, ...board.fading, ...board.caution]) cards.set(cd.term_id, cd);
  // 나이대 곡선은 네이버 데이터랩(한국 검색)이 있는 표제어만 온다 — gen_peaks 가 그 힌트
  const withCurve = [...cards.values()].filter((cd) => (cd.gen_peaks?.length ?? 0) > 0).map((cd) => cd.term_id);
  const trends = new Map<string, Trend | null>(
    await Promise.all(withCurve.map(async (id) => [id, combineCurves(await getGenerationCurves(id))] as const)),
  );
  const newIds = newlyVerified(updates, 7, Date.parse(board.generated_at) || undefined);
  const rowOf = (cd: KeywordCard) => toRow(cd, trends.get(cd.term_id) ?? null, newIds, locale);
  const rowsAll: Record<KeywordList, Row[]> = { rising: board.rising.map(rowOf), fading: board.fading.map(rowOf), caution: board.caution.map(rowOf) };
  const lists: Record<KeywordList, Row[]> = q ? { rising: filterRows(rowsAll.rising, q), fading: filterRows(rowsAll.fading, q), caution: filterRows(rowsAll.caution, q) } : rowsAll;
  const hasCurves = [...trends.values()].some((t) => t && t.spark.length > 1);
  const spot = pickSpotlight(rowsAll.rising);
  const spotCurves = Object.fromEntries(spot.rows.map((r) => [r.id, trends.get(r.id)?.smooth ?? []]));
  const lite: UpdateLite[] = updates.slice(0, 300).map((u) => ({ kind: u.kind, at: u.at, label: u.label, term_id: u.term_id ?? null, region: u.region ?? null }));
  const recommendHref = regions.length ? `/recommend?regions=${encodeURIComponent(regions.join(","))}` : "/recommend";
  const count = board.totals.rising ?? 0;

  return (
    <>
      <div className="fr-head">
        <h1 className="fr-h1">
          {locale === "en" ? (
            <><span className="fr-count fr-num">{count}</span> {c(locale, "headline_prefix")} {regionSentence(locale, regions)}</>
          ) : (
            <>{c(locale, "headline_prefix")} {regionSentence(locale, regions)}{c(locale, "headline_suffix")} <span className="fr-count fr-num">{count}</span>{c(locale, "count_unit")}</>
          )}
        </h1>
        <p className="fr-stamp m-0">
          <span className="fr-num">{fmtDateTime(board.generated_at, locale)}</span> {c(locale, "updated")} <span aria-hidden> · </span> {c(locale, "window_note")}
        </p>
      </div>
      <RegionPicker locale={locale} selected={regions} counts={board.counts} />
      <SinceVisit locale={locale} items={lite} />
      {!q && page === 1 && <Spotlight rows={spot.rows} curves={spotCurves} byGrowth={spot.byGrowth} locale={locale} />}
      <ReportBoard locale={locale} lists={lists} totals={board.totals} page={board.page ?? page} pageSize={board.page_size ?? 30} initialList={list} q={q} regions={regions} hasCurves={hasCurves} />
      <Watchlist locale={locale} rows={[...rowsAll.rising, ...rowsAll.fading, ...rowsAll.caution]} />
      <div className="mt-10 flex flex-wrap items-center gap-3 border-t border-[var(--fr-rule)] pt-6">
        <Link href={recommendHref} className="fr-btn is-primary">{c(locale, "recommend_cta")}</Link>
        <span className="fr-steel text-[13.5px]">{regions.length ? regionSentence(locale, regions) : c(locale, "headline_all")}</span>
      </div>
    </>
  );
}
