/* 이번 주 주목 — 순위가 곧 크기다: 1위는 넓은 표지, 2·3위는 한 칸. 표지에는 밈 낱말이 원문 그대로 크게 서고,
   검색 곡선이 아래에서 솟는다(청록 = 최근 기간, 짙은 회색 = 견준 직전 기간). 썸네일이 있으면 그 자리에 영상 그림을 둔다.
   표 아래 목록은 기본 순(백엔드 순서)이라, 늘어난 순위는 여기 표지가 맡는다. 표지는 표에 없는 것 하나를 더 말한다 —
   가장 많이 늘어난 연령대(누가 더 찾나). 휴대폰은 가로로 넘긴다(줄 안에서만 넘치고 페이지는 옆으로 밀리지 않는다). */
import Link from "next/link";
import type { Locale } from "@/lib/i18n";
import { fmtDay, type Weeks } from "@/lib/lab/o-report";
import { stageWord, tr } from "@/lib/lab/o-report-copy";
import type { SpotItem } from "@/lib/lab/o-report-data";
import { FitName, Growth, RiskMark } from "./bits";
import { SilhouetteShape } from "./charts";

function Cover({ item, rank, lead, locale, weeks, href, delay, refAt }: { item: SpotItem; rank: number | null; lead: boolean; locale: Locale; weeks: Weeks; href: string; delay: number; refAt: string }) {
  const { row, shape, driver } = item;
  const thumb = row.thumb;
  // 낱말 칸의 높이 — 곡선이 있으면 표지의 위 56%, 없으면 거의 전부. 읽기 도움 한 줄이 있으면 그만큼 뺀다
  const avail = `${shape ? "56cqb - 72px" : "100cqb - 84px"}${row.reading ? " - 28px" : ""}`;
  const style = { "--max": lead ? "112px" : "72px", "--avail": `calc(${avail})` } as React.CSSProperties;
  return (
    <Link href={href} className="group block focus-visible:outline-offset-4">
      {/* 곡선이 없는 표지(검색 자료가 없는 지역)는 낮게 — 빈 면이 자리만 차지하지 않게 */}
      <div className={`or-cover ${shape || thumb ? "h-[300px] lg:h-[340px]" : "h-[210px] lg:h-[250px]"}`} style={style}>
        <div className="absolute inset-x-0 top-0 z-[1] flex items-start justify-between gap-3 p-4 sm:p-5">
          {rank != null ? <span className="or-num text-[18px] leading-none font-bold">{rank}</span> : <span />}
          {row.growth != null ? (
            <span className="flex flex-col items-end gap-1 text-right">
              <Growth locale={locale} g={row.growth} size={lead ? "lg" : "md"} />
              {/* 무엇을 견준 숫자인지는 1위 표지에만 — 절 제목이 이미 말한다 */}
              {lead && <span className="text-[12px] text-[var(--or-slate)]">{tr(locale, weeks === 4 ? "spot_caption_4" : "spot_caption_12")}</span>}
            </span>
          ) : row.lastUsed ? (
            /* 검색 자료가 없는 지역: 늘어난 정도 대신 실제로 마지막에 쓰인 날 */
            <span className="flex flex-col items-end gap-1 text-right">
              <span className="or-num text-[16px] leading-none font-semibold">{fmtDay(row.lastUsed, locale, refAt)}</span>
              <span className="text-[12px] text-[var(--or-slate)]">{tr(locale, "last_used")}</span>
            </span>
          ) : null}
        </div>
        {thumb ? (
          <>
            {/* 썸네일은 주소만 — 영상 파일을 받거나 보관하지 않는다 */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={thumb.src} alt="" loading="lazy" className="absolute inset-x-0 bottom-0 h-[58%] w-full object-cover" />
            <div className="absolute inset-x-0 top-[64px] bottom-[58%] flex items-end px-4 pb-2 sm:px-5" style={{ "--avail": "calc(42cqb - 72px)" } as React.CSSProperties}>
              <FitName name={row.name} lang={row.lang} maxLines={2} splitAbove={lead ? 5 : 3.6} className="or-cover-word group-hover:underline group-hover:decoration-2 group-hover:underline-offset-4" />
            </div>
          </>
        ) : (
          <>
            <div className={`absolute inset-x-0 top-[56px] flex flex-col items-start justify-end px-4 pb-3 sm:px-5 ${shape ? "bottom-[44%]" : "bottom-3"}`}>
              <FitName name={row.name} lang={row.lang} splitAbove={lead ? 5 : 3.6} className="or-cover-word group-hover:underline group-hover:decoration-2 group-hover:underline-offset-[6px]" />
              {row.reading && <p lang={row.readingLang} className="mt-1.5 text-[16px] font-medium text-[var(--or-slate)]">{row.reading}</p>}
            </div>
            {shape && <div className="or-cover-shape !h-[44%]"><SilhouetteShape shape={shape} delay={delay} /></div>}
          </>
        )}
      </div>
      <div className="mt-3 pr-2">
        <p lang={row.glossLang} className="or-clamp-2 text-[16px] leading-[1.5] text-[var(--or-ink)]">{row.gloss}</p>
        {driver && (
          <p className="mt-2 flex flex-wrap items-baseline gap-x-2 text-[13px]">
            <span className="text-[var(--or-slate)]">{tr(locale, "driver")}</span>
            <span className="font-semibold">{driver.label}</span>
            <Growth locale={locale} g={driver.change} size="xs" />
          </p>
        )}
        <p className="mt-1.5 flex flex-wrap items-center gap-2 text-[13px] text-[var(--or-slate)]">
          {stageWord(locale, row.lifecycle)}
          <RiskMark risk={row.risk === "caution" || row.risk === "avoid" ? row.risk : null} locale={locale} />
        </p>
      </div>
    </Link>
  );
}

export function Spotlight({ mode, items, locale, weeks, regionName, regionsParam, refAt }: {
  mode: "growth" | "plain" | "flat"; items: SpotItem[]; locale: Locale; weeks: Weeks; regionName: string; regionsParam: string; refAt: string;
}) {
  const q = regionsParam ? `?regions=${encodeURIComponent(regionsParam)}` : "";
  const title = mode === "plain" ? tr(locale, "spot_title_plain", { r: regionName }) : tr(locale, weeks === 4 ? "spot_title_4" : "spot_title_12");
  if (mode === "plain" && !items.length) return null;
  return (
    <section aria-labelledby="or-spot-h" className="pt-8 pb-10">
      <div className="flex flex-wrap items-baseline justify-between gap-x-8 gap-y-2">
        <h2 id="or-spot-h" className="text-[21px] leading-tight font-bold sm:text-[24px]">{title}</h2>
        {/* 표지 곡선의 세 색이 무엇인지 — 청록은 늘 '최근 기간' 이다 */}
        {mode === "growth" && (
          <p className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[13px] text-[var(--or-slate)]">
            <span>{tr(locale, "legend_source")}</span>
            {([["var(--or-petrol)", tr(locale, "legend_recent", { w: weeks })], ["var(--or-base)", tr(locale, "legend_base", { w: weeks })], ["var(--or-context)", tr(locale, "legend_before")]] as const).map(([c, label]) => (
              <span key={label} className="inline-flex items-center gap-1.5">
                <span aria-hidden className="inline-block h-2.5 w-2.5 rounded-[1px]" style={{ background: c }} />
                {label}
              </span>
            ))}
          </p>
        )}
      </div>
      {mode === "plain" && <p className="mt-2 max-w-[720px] text-[14px] leading-[1.55] text-[var(--or-slate)]">{tr(locale, "spot_plain_note")}</p>}
      {mode === "flat" && <p className="mt-3 max-w-[720px] text-[16px] leading-[1.55] text-[var(--or-slate)]">{tr(locale, "spot_none_up")}</p>}
      {items.length > 0 && (
        <ol className="or-snap relative -mx-5 mt-5 flex list-none gap-4 overflow-x-auto scroll-px-5 px-5 pb-1 sm:mx-0 sm:grid sm:grid-cols-3 sm:gap-5 sm:overflow-visible sm:px-0 lg:grid-cols-4">
          {/* relative — 화면 읽기용 글자(sr-only, absolute)가 넘기는 줄 밖으로 새어 페이지를 옆으로 밀지 않게 */}
          {items.map((it, i) => (
            <li key={it.row.id} className={`w-[84%] shrink-0 sm:w-auto ${i === 0 ? "lg:col-span-2" : ""}`}>
              <Cover item={it} rank={mode === "growth" ? it.row.rank : null} lead={i === 0} locale={locale} weeks={weeks} delay={i * 120} refAt={refAt}
                href={`/lab/o-report/m/${encodeURIComponent(it.row.id)}${q}`} />
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
