/* 항목 화면의 쓰임 추이 — 큰 그림 하나(증감을 센 연령대의 평균, 7일 평균)와 연령대별 작은 그림 다섯, 그리고 같은 숫자의 표.
   큰 그림은 '최근 4주' 와 '직전 4주' 를 띠로 깔아, 증감 숫자가 어느 두 기간을 견준 것인지 그림으로 보인다.
   검색이 드물어 셈에서 뺀 연령대는 작은 그림에 그 이유(검색이 있던 날 수)를 적는다 — 숫자가 어디서 왔는지 숨기지 않는다. */
import type { LabLocale as Locale } from "@/lib/i18n";
import { fmtDay, fmtGrowth } from "@/lib/lab/o-report";
import { tr } from "@/lib/lab/o-report/copy";
import type { EntryTrend } from "@/lib/lab/o-report/data";
import { Growth } from "./bits";
import { Sparkline } from "./charts";

const DAY = 86_400_000;

const joinGens = (locale: Locale, gens: string[]) => (locale === "ko" ? gens.join("·") : gens.length > 1 ? `${gens.slice(0, -1).join(", ")} and ${gens.at(-1)}` : gens[0] ?? "");

export function IndexChart({ trend, locale }: { trend: EntryTrend; locale: Locale }) {
  // 선과 면만 SVG(가로세로를 늘려 그린다, 선 굵기는 그대로), 글자는 모두 HTML — 휴대폰에서도 12px 로 읽힌다
  const n = trend.daily.length;
  const top = 100;   // 지수의 천장 그대로 — 연령대 평균은 100 에 닿지 않는다(연령대마다 최고점이 다른 날이라)
  const pct = (i: number) => (i / Math.max(1, n - 1)) * 100;
  const X = (i: number) => pct(i) * 10;
  const Y = (v: number) => (1 - Math.min(v, top) / top) * 100;
  const path = trend.daily.map((v, i) => `${i ? "L" : "M"}${X(i).toFixed(1)},${Y(v).toFixed(2)}`).join("");
  const area = `${path} L1000,100 L0,100 Z`;
  const start = Date.parse(`${trend.start}T00:00:00Z`);
  // 달이 바뀌는 날에 눈금 (양 끝에 너무 붙은 것은 글자가 잘리므로 뺀다)
  const ticks: { i: number; label: string }[] = [];
  for (let i = 0; i < n; i++) {
    const d = new Date(start + i * DAY);
    if (d.getUTCDate() === 1 && pct(i) > 3 && pct(i) < 97) ticks.push({ i, label: locale === "ko" ? `${d.getUTCMonth() + 1}월` : d.toLocaleString("en-US", { month: "short", timeZone: "UTC" }) });
  }
  const w4 = 28;
  const showWindows = trend.growth4 != null && n > w4 * 2;
  const baseAt = pct(n - w4 * 2), recentAt = pct(n - w4);
  const gens = joinGens(locale, trend.averaged);
  const summary = [
    tr(locale, "trend_all", { gens }),
    tr(locale, "trend_range", { from: fmtDay(trend.start, locale), to: fmtDay(trend.end, locale) }),
    trend.growth4 != null ? tr(locale, "trend_growth", { w: 4, g: fmtGrowth(trend.growth4) }) : null,
  ].filter(Boolean).join(". ");
  return (
    <figure className="min-w-0">
      <div className="pl-9">
        <div role="img" aria-label={summary} className="relative h-[220px] sm:h-[260px]">
          {showWindows && (
            <div aria-hidden>
              <div className="absolute inset-y-0 bg-[var(--or-mist)]" style={{ left: `${baseAt}%`, width: `${recentAt - baseAt}%` }} />
              <div className="absolute inset-y-0 right-0 bg-[var(--or-petrol-tint)]" style={{ left: `${recentAt}%` }} />
              {/* 띠 이름은 띠의 오른쪽 끝에 붙인다 — 휴대폰에서 띠가 50px 남짓이라 왼쪽에서 시작하면 화면 밖으로 잘린다 */}
              <span className="absolute top-1.5 pr-1.5 text-[12px] whitespace-nowrap text-[var(--or-slate)]" style={{ right: `${100 - recentAt}%` }}>{tr(locale, "trend_base", { w: 4 })}</span>
              <span className="absolute top-1.5 right-0 pr-1.5 text-[12px] font-semibold whitespace-nowrap text-[var(--or-petrol-deep)]">{tr(locale, "trend_window", { w: 4 })}</span>
            </div>
          )}
          <div className="absolute inset-x-0 top-8 bottom-0" aria-hidden>
            {[0, 50, 100].map((g) => (
              <span key={g} className="or-num absolute -left-9 w-7 -translate-y-1/2 text-right text-[12px] leading-none text-[var(--or-slate)]" style={{ top: `${Y(g)}%` }}>{g}</span>
            ))}
            <svg viewBox="0 0 1000 100" preserveAspectRatio="none" className="absolute inset-0 h-full w-full overflow-visible" focusable="false">
              {[0, 50, 100].map((g) => (
                <line key={g} x1="0" x2="1000" y1={Y(g)} y2={Y(g)} stroke={g === 0 ? "var(--or-line-strong)" : "var(--or-line)"} strokeWidth="1" vectorEffect="non-scaling-stroke" />
              ))}
              <path d={area} fill="var(--or-petrol)" opacity="0.08" />
              <path d={path} fill="none" stroke="var(--or-petrol)" strokeWidth="2" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
            </svg>
          </div>
        </div>
        <div className="relative mt-1.5 h-4" aria-hidden>
          {ticks.map((t) => (
            <span key={t.i} className="absolute -translate-x-1/2 text-[12px] leading-none text-[var(--or-slate)]" style={{ left: `${pct(t.i)}%` }}>{t.label}</span>
          ))}
        </div>
      </div>
      <figcaption className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-[var(--or-slate)]">
        <span>{tr(locale, "trend_axis", { gens })}</span>
        <span className="or-num">{tr(locale, "trend_range", { from: fmtDay(trend.start, locale), to: fmtDay(trend.end, locale) })}</span>
      </figcaption>
    </figure>
  );
}

export function GenGrid({ trend, locale }: { trend: EntryTrend; locale: Locale }) {
  if (trend.gens.length < 2) return null;
  return (
    <div className="mt-8">
      <h3 className="text-[16px] font-bold">{tr(locale, "trend_gen_title")}</h3>
      <p className="mt-1 max-w-[680px] text-[13px] leading-[1.55] text-[var(--or-slate)]">{tr(locale, "trend_gen_note")}</p>
      <ul className="mt-4 grid grid-cols-2 gap-x-6 gap-y-6 sm:grid-cols-3 lg:grid-cols-5">
        {trend.gens.map((g) => {
          const out = trend.growth4 != null && !g.used;   // 증감을 세는데 이 연령대는 뺐다
          return (
            <li key={g.gen} className="min-w-0 border-t border-[var(--or-line)] pt-3">
              <p className="flex items-baseline justify-between gap-2">
                <span className="text-[14px] font-semibold">{g.label}</span>
                {g.growth != null && <Growth locale={locale} g={g.growth} />}
              </p>
              <div className={`mt-2 ${out ? "opacity-60" : ""}`}><Sparkline values={g.weeklyValues} recent={4} className="!h-10 !w-full" /></div>
              {out
                ? <p className="mt-1.5 text-[12px] leading-[1.45] text-[var(--or-slate)]">{tr(locale, "trend_gen_out", { r: g.daysRecent, b: g.daysBase })}</p>
                : g.peak && <p className="or-num mt-1.5 text-[12px] text-[var(--or-slate)]">{tr(locale, "trend_gen_peak", { d: fmtDay(g.peak, locale) })}</p>}
            </li>
          );
        })}
      </ul>
      {/* 같은 숫자를 표로 — 그림을 읽기 어려운 사람과 숫자를 옮겨 적을 사람을 위해 */}
      <details className="or-table-view mt-6">
        <summary className="inline-flex h-10 cursor-pointer items-center text-[14px] font-medium text-[var(--or-petrol)] underline-offset-4 hover:underline">{tr(locale, "table_view")}</summary>
        <div className="mt-2 overflow-x-auto">
          <table className="w-full min-w-[520px] border-collapse text-left text-[14px]">
            <thead>
              <tr className="border-b border-[var(--or-ink)] text-[13px] text-[var(--or-slate)]">
                <th scope="col" className="py-2 pr-4 font-medium">{tr(locale, "col_gen")}</th>
                <th scope="col" className="py-2 pr-4 text-right font-medium">{tr(locale, "col_recent_avg")}</th>
                <th scope="col" className="py-2 pr-4 text-right font-medium">{tr(locale, "col_base_avg")}</th>
                <th scope="col" className="py-2 pr-4 text-right font-medium">{tr(locale, "col_change")}</th>
                <th scope="col" className="py-2 pr-4 text-right font-medium">{tr(locale, "col_days")}</th>
                <th scope="col" className="py-2 font-medium">{tr(locale, "col_peak")}</th>
              </tr>
            </thead>
            <tbody className="or-num">
              {trend.gens.map((g) => (
                <tr key={g.gen} className="border-b border-[var(--or-line)]">
                  <th scope="row" className="py-2 pr-4 text-left font-semibold" style={{ fontFamily: "var(--font-pretendard)" }}>{g.label}</th>
                  <td className="py-2 pr-4 text-right">{g.recentAvg ?? "–"}</td>
                  <td className="py-2 pr-4 text-right">{g.baseAvg ?? "–"}</td>
                  <td className="py-2 pr-4 text-right">{g.growth != null ? fmtGrowth(g.growth) : "–"}</td>
                  <td className="py-2 pr-4 text-right">{tr(locale, "days_pair", { r: g.daysRecent, b: g.daysBase })}</td>
                  <td className="py-2">{g.peak ? fmtDay(g.peak, locale) : "–"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
