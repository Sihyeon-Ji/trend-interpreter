import Link from "next/link";
import { Board } from "@/components/lab/o-report/board";
import { ReportHead } from "@/components/lab/o-report/report-head";
import { SinceVisit } from "@/components/lab/o-report/since-visit";
import { Spotlight } from "@/components/lab/o-report/spotlight";
import type { Current } from "@/components/lab/o-report/store";
import type { Locale } from "@/lib/i18n";
import { fmtDay, minDays, type ListKey, type SortKey, type Weeks } from "@/lib/lab/o-report";
import { tr } from "@/lib/lab/o-report/copy";
import { KNOWN_REGIONS, loadReport, parseRegions, type Report } from "@/lib/lab/o-report/data";
import { regionLabel } from "@/lib/labels";
import { getLocale } from "@/lib/locale";
import { TARGET_REGIONS } from "@/lib/reader";

/* 초안 1 첫 화면 — '지금 [지역]에서 쓰이는 밈'. 주 단위 계획(쓰이는·식는·조심할), 매일 확인(지난 방문 이후), 쓰기 전 확인(미리보기·찾기),
   만들기(이 밈으로 만들기·추천받기), 지켜보기(무엇이 바뀌었나).
   주소: ?regions=KR,JP|all &w=4|12 &tab=rising|fading|caution|watch &sort=gain &page=n &m=<밈 id> */

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
    searchable ? tr(locale, "method_enough", { d: minDays(weeks * 7), total: weeks * 7 }) : null,
    searchable ? tr(locale, weeks === 4 ? "method_rank" : "method_rank_12", { w: weeks }) : null,
    searchable && range ? tr(locale, "method_dates", { from: fmtDay(range.from, locale), to: fmtDay(range.to, locale) }) : null,
    tr(locale, "method_risk"),
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

/** 확인된 밈이 없는(또는 사용 자제 밈뿐인) 지역 — 비었다고 숨기지 않고 까닭과 갈 곳을 준다: 전체, 밈이 있는 지역, 사전 */
function EmptyRegion({ locale, report, keep, avoidOnly }: { locale: Locale; report: Report; keep: string; avoidOnly: boolean }) {
  const q = (regions: string) => { const u = new URLSearchParams(keep); u.set("regions", regions); return `/lab/o-report?${u}`; };
  const others = ["KR", "JP", "GLOBAL"].filter((r) => !report.asked.includes(r) && (report.counts[r] ?? 0) > 0);
  return (
    <div className="mt-2 pb-8">
      {avoidOnly && <p className="max-w-[720px] text-[16px] leading-[1.6] text-[var(--or-ink)]">{tr(locale, "empty_avoid", { n: report.totals.caution })}</p>}
      {report.spikes > 0 && <p className="mt-2 max-w-[720px] text-[14px] leading-[1.6] text-[var(--or-slate)]">{tr(locale, "empty_spikes", { n: report.spikes })}</p>}
      <p className="mt-5 flex flex-wrap gap-2">
        <Link href={q("all")} className="inline-flex h-11 items-center rounded-[6px] bg-[var(--or-ink)] px-4 text-[14px] font-semibold whitespace-nowrap text-white hover:bg-[var(--or-petrol-deep)]">{tr(locale, "empty_all")}</Link>
        {others.map((r) => (
          <Link key={r} href={q(r)} className="inline-flex h-11 items-center gap-2 rounded-[6px] border border-[var(--or-line-strong)] px-4 text-[14px] font-medium whitespace-nowrap hover:border-[var(--or-ink)]">
            {regionLabel(locale, r)} <span className="or-num text-[var(--or-slate)]">{report.counts[r]}</span>
          </Link>
        ))}
        <Link href="/lab/o-report/search" className="inline-flex h-11 items-center rounded-[6px] border border-[var(--or-line-strong)] px-4 text-[14px] font-medium whitespace-nowrap hover:border-[var(--or-ink)]">{tr(locale, "empty_dictionary")}</Link>
      </p>
    </div>
  );
}

export default async function OReportHome({ searchParams }: { searchParams: Promise<Search> }) {
  const [sp, locale] = await Promise.all([searchParams, getLocale()]);
  const asked = parseRegions(sp.regions);
  const weeks: Weeks = one(sp.w) === "12" ? 12 : 4;
  const page = Math.max(1, Number.parseInt(one(sp.page), 10) || 1);
  const tabParam = one(sp.tab) as ListKey;
  const tab: ListKey = LIST_KEYS.includes(tabParam) ? tabParam : "rising";
  const sort: SortKey = one(sp.sort) === "gain" ? "gain" : "base";
  const m = one(sp.m) || null;

  const report = await loadReport(asked, weeks, page, locale, { tab, sort, m });   // 서버가 답하지 않으면 error.tsx
  // 쓰이는·식는 밈이 없고 조심할 밈만 있는 지역(홍콩: 사용 자제 1개)은 조심할 밈 목록을 먼저 편다
  const avoidOnly = report.known > 0 && report.totals.rising === 0 && report.totals.fading === 0 && report.totals.caution > 0;
  const firstTab: ListKey = avoidOnly && !tabParam ? "caution" : tab;
  const firstPick = firstTab !== tab && !m ? report.lists.caution[0]?.id ?? null : report.selectedId;

  const regionsParam = one(sp.regions) ? (asked.length ? asked.join(",") : "all") : "";
  const name = regionName(locale, asked);
  const globalOnly = asked.length === 1 && asked[0] === "GLOBAL";

  const query = (over: Record<string, string | null>) => {
    const q = new URLSearchParams();
    if (regionsParam) q.set("regions", regionsParam);
    if (weeks === 12) q.set("w", "12");
    if (tab !== "rising") q.set("tab", tab);
    if (sort === "gain") q.set("sort", "gain");
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
  // 지난 방문 줄이 지켜보는 밈의 지금 단계·쓸 때 조심을 알 수 있게 — 목록 전체 대신 두 칸만
  const current: Record<string, Current> = {};
  for (const r of [...report.lists.rising, ...report.lists.fading, ...report.lists.caution]) current[r.id] ??= { lifecycle: r.lifecycle, risk: r.risk };

  return (
    <div className="mx-auto max-w-[1320px] px-5 sm:px-8">
      <ReportHead
        locale={locale} regionName={name} globalOnly={globalOnly} options={options} picked={asked.length ? asked : TARGET_REGIONS}
        keepForRegion={keepForRegion.toString()} known={report.known} totals={report.totals} weeks={weeks}
        periodHref={(w) => query({ w: w === 12 ? "12" : null, page: null, m: null })} updatedAt={report.generatedAt} recommendHref={recommendHref} searchable={report.searchable}
        cautionHref={`${query({ tab: "caution", page: null, m: null, sort: null })}#or-board`} />
      {(report.known === 0 || avoidOnly) && <EmptyRegion locale={locale} report={report} keep={keep.toString()} avoidOnly={avoidOnly} />}
      <SinceVisit locale={locale} changes={report.changes} regionsParam={regionsParam} current={current} />
      {report.known > 0 && (
        <Spotlight mode={report.spotlight.mode} items={report.spotlight.items} locale={locale} weeks={weeks} regionName={name} regionsParam={regionsParam} refAt={report.generatedAt} />
      )}
      {/* 표지가 없으면(검색 자료도, 쓰이는 밈도 없는 지역) 목록이 바로 줄 밑에 붙지 않게 띄운다 */}
      {report.known > 0 && report.spotlight.mode === "plain" && !report.spotlight.items.length && <div className="h-8" aria-hidden />}
      {report.known > 0 && (
        <Board
          locale={locale} lists={report.lists} totals={report.totals} previews={report.previews} searchable={report.searchable} weeks={weeks} ranked={report.ranked}
          regionsParam={regionsParam} page={report.page} pageSize={report.pageSize} initialTab={firstTab} initialSort={sort} initialSelected={firstPick}
          changes={report.changes} keep={keep.toString()} refAt={report.generatedAt} />
      )}
      <Method locale={locale} weeks={weeks} range={report.dataRange} searchable={report.searchable} />
    </div>
  );
}
