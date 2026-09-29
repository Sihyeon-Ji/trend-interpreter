import { Board } from "@/components/lab/o-report/board";
import { ReportHead } from "@/components/lab/o-report/report-head";
import { SinceVisit } from "@/components/lab/o-report/since-visit";
import { Spotlight } from "@/components/lab/o-report/spotlight";
import type { Locale } from "@/lib/i18n";
import { fmtDay, type ListKey, type Weeks } from "@/lib/lab/o-report";
import { tr } from "@/lib/lab/o-report-copy";
import { KNOWN_REGIONS, loadReport, parseRegions } from "@/lib/lab/o-report-data";
import { regionLabel } from "@/lib/labels";
import { getLocale } from "@/lib/locale";
import { TARGET_REGIONS } from "@/lib/reader";

/* 초안 1 첫 화면 — '지금 [지역]에서 뜨는 밈'. 주 단위 계획(뜨는·식는·조심할), 매일 확인(지난 방문 이후), 쓰기 전 확인(미리보기·찾기),
   만들기(이 밈으로 만들기·추천받기), 지켜보기. 주소: ?regions=KR,JP|all &w=4|12 &tab=rising|fading|caution|watch &page=n &m=<밈 id> */

type Search = Record<string, string | string[] | undefined>;
const one = (v: string | string[] | undefined) => [v].flat().filter(Boolean)[0] ?? "";
const LIST_KEYS: ListKey[] = ["rising", "fading", "caution", "watch"];

/* 제목은 레이아웃의 기본값('트렌드 리포트 | 트렌드 통역') — 같은 구간의 페이지에는 레이아웃 template 이 붙지 않는다 */

function regionName(locale: Locale, asked: string[]): string {
  if (!asked.length) return tr(locale, "region_all");
  const names = asked.map((r) => regionLabel(locale, r));
  if (names.length <= 2) return names.join(", ");
  return tr(locale, "region_more", { first: names[0], n: names.length - 1 });
}

function Method({ locale, weeks, range, searchable }: { locale: Locale; weeks: Weeks; range: { from: string; to: string } | null; searchable: boolean }) {
  // 검색 곡선을 쓰지 않는 지역(한국이 빠진 선택)에는 증감·순위 설명을 붙이지 않는다 — 화면에 없는 숫자의 설명이다
  const paras = [
    tr(locale, "method_list"),
    searchable ? tr(locale, "method_growth", { w: weeks }) : tr(locale, "method_no_search"),
    searchable ? tr(locale, "method_enough") : null,
    searchable ? tr(locale, weeks === 4 ? "method_rank" : "method_rank_12", { w: weeks }) : null,
    searchable && range ? tr(locale, "method_dates", { from: fmtDay(range.from, locale), to: fmtDay(range.to, locale) }) : null,
    tr(locale, "method_sources"),
  ].filter(Boolean) as string[];
  return (
    <section aria-labelledby="or-method-h" className="mt-16 grid gap-4 border-t border-[var(--or-line)] pt-8 pb-16 lg:grid-cols-[260px_minmax(0,1fr)] lg:gap-12">
      <h2 id="or-method-h" className="text-[16px] font-bold">{tr(locale, "method_title")}</h2>
      <div className="max-w-[760px] space-y-2.5 text-[14px] leading-[1.65] text-[var(--or-slate)]">
        {paras.map((t) => <p key={t}>{t}</p>)}
      </div>
    </section>
  );
}

export default async function OReportHome({ searchParams }: { searchParams: Promise<Search> }) {
  const [sp, locale] = await Promise.all([searchParams, getLocale()]);
  const asked = parseRegions(sp.regions);
  const weeks: Weeks = one(sp.w) === "12" ? 12 : 4;
  const page = Math.max(1, Number.parseInt(one(sp.page), 10) || 1);
  const tabParam = one(sp.tab) as ListKey;
  const tab: ListKey = LIST_KEYS.includes(tabParam) ? tabParam : "rising";
  const m = one(sp.m);

  const report = await loadReport(asked, weeks, page, locale);   // 서버가 답하지 않으면 error.tsx

  const regionsParam = one(sp.regions) ? (asked.length ? asked.join(",") : "all") : "";
  const name = regionName(locale, asked);
  const globalOnly = asked.length === 1 && asked[0] === "GLOBAL";

  const query = (over: Record<string, string | null>) => {
    const q = new URLSearchParams();
    if (regionsParam) q.set("regions", regionsParam);
    if (weeks === 12) q.set("w", "12");
    if (tab !== "rising") q.set("tab", tab);
    for (const [k, v] of Object.entries(over)) { if (v == null) q.delete(k); else q.set(k, v); }
    const s = q.toString();
    return s ? `/lab/o-report?${s}` : "/lab/o-report";
  };
  const keep = new URLSearchParams();
  if (regionsParam) keep.set("regions", regionsParam);
  if (weeks === 12) keep.set("w", "12");
  const keepForRegion = new URLSearchParams();
  if (weeks === 12) keepForRegion.set("w", "12");
  if (tab !== "rising") keepForRegion.set("tab", tab);

  const targets = (asked.length ? asked : TARGET_REGIONS).filter((r) => r !== "GLOBAL");
  const recommendHref = `/recommend${targets.length ? `?regions=${targets.join(",")}` : ""}`;
  const options = KNOWN_REGIONS.map((code) => ({ code, label: regionLabel(locale, code), count: report.counts[code] ?? 0 }));

  return (
    <div className="mx-auto max-w-[1320px] px-5 sm:px-8">
      <ReportHead
        locale={locale} regionName={name} globalOnly={globalOnly} options={options} picked={asked.length ? asked : TARGET_REGIONS}
        keepForRegion={keepForRegion.toString()} known={report.known} totals={report.totals} weeks={weeks}
        periodHref={(w) => query({ w: w === 12 ? "12" : null, page: null, m: null })} updatedAt={report.generatedAt} recommendHref={recommendHref} searchable={report.searchable}
        cautionHref={`${query({ tab: "caution", page: null, m: null })}#or-board`} />
      <SinceVisit locale={locale} changes={report.changes} regionsParam={regionsParam} />
      {report.known > 0 && (
        <Spotlight mode={report.spotlight.mode} items={report.spotlight.items} locale={locale} weeks={weeks} regionName={name} regionsParam={regionsParam} refAt={report.generatedAt} />
      )}
      {report.known > 0 && (
        <Board
          locale={locale} lists={report.lists} totals={report.totals} previews={report.previews} searchable={report.searchable} weeks={weeks}
          regionsParam={regionsParam} page={report.page} pageSize={report.pageSize} initialTab={tab} initialSelected={m || null}
          changes={report.changes} keep={keep.toString()} refAt={report.generatedAt} />
      )}
      <Method locale={locale} weeks={weeks} range={report.dataRange} searchable={report.searchable} />
    </div>
  );
}
