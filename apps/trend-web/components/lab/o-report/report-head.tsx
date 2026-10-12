/* 리포트 머리 — 지역이 제목이자 조작부. 한 문장 요약(실제 수), 비교 기간, 갱신 시각, 추천받기. 제목 위에 라벨을 얹지 않는다. */
import Link from "next/link";
import type { LabLocale as Locale } from "@/lib/i18n";
import { fmtTime, type Weeks } from "@/lib/lab/o-report";
import { tr } from "@/lib/lab/o-report/copy";
import { RegionPicker, type RegionOption } from "./region-picker";
import { TabJump } from "./tab-jump";

export function ReportHead({ locale, regionName, globalOnly, options, picked, keepForRegion, known, totals, weeks, periodHref, updatedAt, recommendHref, cautionHref, searchable }: {
  locale: Locale;
  searchable: boolean;           // 기간을 바꿔 볼 검색 곡선이 있나 — 없으면 기간 고르기를 내지 않는다
  regionName: string;
  globalOnly: boolean;
  options: RegionOption[];
  picked: string[];
  keepForRegion: string;
  known: number;
  totals: { rising: number; fading: number; caution: number };
  weeks: Weeks;
  periodHref: (w: Weeks) => string;
  updatedAt: string;
  recommendHref: string;
  cautionHref: string;
}) {
  // 제목 문장을 지역 자리에서 갈라 그 자리에 조작부를 끼운다
  const template = locale === "en" && globalOnly ? "Memes in use {r} now" : tr(locale, "head_title", { r: "{r}" });
  const [before, after] = template.split("{r}");
  const summary = known === 0
    ? tr(locale, "head_summary_empty", { r: regionName })
    : tr(locale, "head_summary", { r: regionName, n: known, rising: totals.rising, fading: totals.fading });

  return (
    <section className="pt-8 pb-6 sm:pt-12">
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
        <div className="min-w-0">
          <h1 className="or-headline">
            {before}
            <RegionPicker locale={locale} label={regionName} options={options} picked={picked} keep={keepForRegion} />
            {after}
          </h1>
          <p className="mt-4 max-w-[720px] text-[16px] leading-[1.6] text-[var(--or-slate)] sm:text-[18px]">
            {summary}{known === 0 && <> {tr(locale, "empty_body")}</>}
            {/* '무엇을 피해야 하나' 는 주간 계획의 셋째 질문 — 조심할 밈 목록으로 곧장 */}
            {known > 0 && totals.caution > 0 && (
              <> <TabJump tab="caution" href={cautionHref}
                className="text-[var(--or-ink)] underline decoration-[var(--or-line-strong)] decoration-1 underline-offset-4 hover:decoration-[var(--or-ink)]">
                {tr(locale, "head_summary_caution", { n: totals.caution })}
              </TabJump></>
            )}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-x-5 gap-y-3 lg:flex-col lg:items-end">
          {searchable && <div role="group" aria-label={tr(locale, "period_label")} className="inline-flex rounded-[6px] border border-[var(--or-line-strong)] p-0.5">
            {([4, 12] as const).map((w) => (
              <Link key={w} href={periodHref(w)} aria-current={w === weeks ? "true" : undefined} scroll={false}
                className={`inline-flex h-9 items-center rounded-[4px] px-3 text-[14px] ${w === weeks ? "bg-[var(--or-mist)] font-semibold text-[var(--or-ink)] shadow-[inset_0_-2px_0_var(--or-petrol)]" : "text-[var(--or-slate)] hover:text-[var(--or-ink)]"}`}>
                {tr(locale, w === 4 ? "period_4" : "period_12")}
              </Link>
            ))}
          </div>}
          <p className="text-[13px] text-[var(--or-slate)]"><span className="or-num">{tr(locale, "head_updated", { t: fmtTime(updatedAt, locale) })}</span></p>
          <Link href={recommendHref} className="inline-flex h-11 items-center rounded-[6px] border border-[var(--or-ink)] px-4 text-[14px] font-semibold text-[var(--or-ink)] hover:bg-[var(--or-ink)] hover:text-white">
            {tr(locale, "cta_recommend")}
          </Link>
        </div>
      </div>
    </section>
  );
}
