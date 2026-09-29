import Link from "next/link";
import type { Metadata } from "next";
import { RegionPicker } from "@/components/lab/f-report/region-picker";
import { ReportBoard } from "@/components/lab/f-report/report-board";
import { SinceVisit, type UpdateLite } from "@/components/lab/f-report/since-visit";
import { Spotlight, type SpotCurve } from "@/components/lab/f-report/spotlight";
import { Watchlist } from "@/components/lab/f-report/watchlist";
import { getGenerationCurves, getKeywordBoard, getUpdateFeed } from "@/lib/data";
import { langTag } from "@/lib/lang";
import { c, parseRegions, regionSentence, regionsParam } from "@/lib/lab/f-report-copy";
import { combineCurves, filterRows, newlyVerified, pickSpotlight, toRow, type Row, type Trend } from "@/lib/lab/f-report";
import { fmtDateTime } from "@/lib/labels";
import { getLocale } from "@/lib/locale";
import type { KeywordCard, KeywordList } from "@/lib/types";

type Search = { regions?: string | string[]; page?: string; q?: string; list?: string };

function parse(sp: Search) {
  const regions = parseRegions(sp.regions);
  const page = Math.max(1, Number.parseInt(sp.page ?? "1", 10) || 1);
  const q = (sp.q ?? "").trim().slice(0, 60);
  const list: KeywordList = sp.list === "fading" || sp.list === "caution" ? sp.list : "rising";
  return { regions, page, q, list };
}

export async function generateMetadata({ searchParams }: { searchParams: Promise<Search> }): Promise<Metadata> {
  const [locale, sp] = await Promise.all([getLocale(), searchParams]);
  const { regions } = parse(sp);
  const where = regionSentence(locale, regions);
  return { title: locale === "ko" ? `지금 ${where}에서 쓰이는 밈 · 트렌드 통역` : `Memes in use now in ${where} · Trend Interpreter` };
}

/** 표지 곡선: 7일 평균을 이틀마다 한 점으로 — 끝에서 recent 점이 최근 4주, 그 앞 base 점이 비교한 4주 */
function spotCurve(t: Trend): SpotCurve {
  const values: number[] = [];
  for (let i = t.smooth.length - 1; i >= 0; i -= 2) values.unshift(t.smooth[i]);
  return { values, recent: Math.ceil(t.recentDays / 2), base: Math.ceil(t.baseDays / 2) };
}

/** 리포트 홈. 시장이 머리이고, 목록은 대시보드(규칙이 매긴 순서), 추이는 한국이 들어 있을 때만 네이버 데이터랩 나이대 곡선에서 계산한다. */
export default async function FReportHome({ searchParams }: { searchParams: Promise<Search> }) {
  const [locale, sp] = await Promise.all([getLocale(), searchParams]);
  const { regions, page, q, list } = parse(sp);
  const [board, feed] = await Promise.all([getKeywordBoard(regions, page), getUpdateFeed(168).catch(() => null)]);
  const feedItems = feed?.items ?? [];
  const boardAt = Date.parse(board.generated_at) || undefined;

  // 세 목록의 카드를 한 번씩만 — 주의 밈은 쓰이는·식는 목록에도 있다
  const cards = new Map<string, KeywordCard>();
  for (const cd of [...board.rising, ...board.fading, ...board.caution]) cards.set(cd.term_id, cd);
  // 나이대 곡선은 네이버 데이터랩(한국 검색)이라 한국이 든 리포트에서만 받는다 — 일본 시장의 밈에 한국 검색 곡선을 붙이지 않는다
  const searchable = regions.length === 0 || regions.includes("KR");
  const withCurve = searchable ? [...cards.values()].filter((cd) => (cd.gen_peaks?.length ?? 0) > 0).map((cd) => cd.term_id) : [];
  const trends = new Map<string, Trend | null>(
    await Promise.all(withCurve.map(async (id) => [id, combineCurves(await getGenerationCurves(id), board.generated_at)] as const)),
  );
  const newIds = newlyVerified(feedItems, 7, boardAt);
  const rowOf = (l: KeywordList) => (cd: KeywordCard) => toRow(cd, trends.get(cd.term_id) ?? null, newIds, locale, l);
  const rowsAll: Record<KeywordList, Row[]> = { rising: board.rising.map(rowOf("rising")), fading: board.fading.map(rowOf("fading")), caution: board.caution.map(rowOf("caution")) };
  const lists: Record<KeywordList, Row[]> = q ? { rising: filterRows(rowsAll.rising, q), fading: filterRows(rowsAll.fading, q), caution: filterRows(rowsAll.caution, q) } : rowsAll;
  const hasCurves = searchable && [...trends.values()].some((t) => t && t.pct !== null);
  const spot = pickSpotlight(rowsAll.rising, rowsAll.fading);
  const spotCurves: Record<string, SpotCurve> = {};
  for (const r of spot.rows) { const t = trends.get(r.id); if (t && t.pct !== null) spotCurves[r.id] = spotCurve(t); }

  // 지난 방문 띠의 재료: 고른 시장의 것만. 새 밈·뜻 바뀜은 대시보드 카드(쓰는 나라)로, 검색 급증은 그 시장의 것으로 가른다.
  const want = new Set(regions);
  const scoped = regions.length > 0;
  const lite: UpdateLite[] = [];
  for (const i of feedItems) {
    if (i.kind === "spike") {
      if (scoped && (!i.region || !want.has(i.region))) continue;
      lite.push({ kind: i.kind, at: i.at, label: i.label, term_id: null, region: i.region ?? null });
    } else if (i.kind === "verified" || i.kind === "meaning_changed") {
      if (!i.term_id) continue;
      if (scoped && !(i.card?.regions ?? []).some((r) => want.has(r))) continue;
      lite.push({ kind: i.kind, at: i.at, label: i.card?.canonical ?? i.label, term_id: i.term_id, region: null, lang: langTag(i.card?.lang) ?? null });
    }
  }
  const rp = regionsParam(regions);
  const recommendHref = regions.length ? `/recommend?regions=${encodeURIComponent(regions.join(","))}` : "/recommend";
  const count = board.totals.rising ?? 0;
  const where = regionSentence(locale, regions);

  return (
    <>
      <div className="fr-head">
        <h1 className="fr-h1">
          {locale === "en"
            ? <><span className="fr-num">{count}</span> {c(locale, "headline_prefix")} {where}</>
            : <>{c(locale, "headline_prefix")} {where}{c(locale, "headline_suffix")} <span className="fr-num">{count}</span>{c(locale, "count_unit")}</>}
        </h1>
        <div className="fr-stamp">
          <span className="fr-num">{fmtDateTime(board.generated_at, locale)}</span> {c(locale, "updated")}
          {hasCurves && <span className="block">{c(locale, "window_note")}</span>}
        </div>
      </div>
      <RegionPicker locale={locale} selected={regions} counts={board.counts} />
      <SinceVisit locale={locale} items={lite.slice(0, 300)} scoped={scoped} />
      {!q && page === 1 && <Spotlight rows={spot.rows} curves={spotCurves} byGrowth={spot.byGrowth} locale={locale} />}
      <ReportBoard locale={locale} lists={lists} totals={board.totals} page={board.page ?? page} pageSize={board.page_size ?? 30} initialList={list} q={q} regionsParam={rp} hasCurves={hasCurves} />
      <Watchlist locale={locale} rows={[...rowsAll.rising, ...rowsAll.fading, ...rowsAll.caution]} />
      <div className="fr-cta">
        <Link href={recommendHref} className="fr-btn is-primary">{c(locale, "recommend_cta")}</Link>
        <span className="fr-steel text-[13.5px]">{where}</span>
      </div>
    </>
  );
}
