import type { Locale } from "@/lib/i18n";
import { fe } from "@/lib/lab/f-editorial-copy";
import { fmtPct, type SearchTrend } from "@/lib/lab/f-editorial";
import { L } from "@/lib/labels";
import type { GenerationCurve } from "@/lib/trends/types";

/* 손으로 그린 SVG 두 가지. 선은 한 색(코발트, 표지에서는 흰색), 값은 글자 색으로 적는다 — 색으로 방향을 말하지 않는다. */

const ORDER = ["10s", "20s", "30s", "40s", "50s+"];
const ym = (d: string) => d.slice(0, 7).replace("-", ".");
const path = (xs: number[], ys: number[]) => xs.map((x, i) => `${i ? "L" : "M"}${x.toFixed(1)},${ys[i].toFixed(1)}`).join(" ");

/** 카드의 작은 추세선 — 주 평균, 마지막 점만 찍는다. 값(%)은 옆에 글자로. */
export function Sparkline({ trend, locale }: { trend: SearchTrend; locale: Locale }) {
  const W = 84, H = 26, pad = 3;
  const v = trend.weekly;
  const max = Math.max(1, ...v), min = Math.min(...v);
  const span = Math.max(1, max - min);
  const xs = v.map((_, i) => pad + (i / Math.max(1, v.length - 1)) * (W - pad * 2));
  const ys = v.map((y) => pad + (1 - (y - min) / span) * (H - pad * 2));
  const label = trend.pct === null ? fe(locale, "search_change_caption") : `${fe(locale, "search_change", { pct: fmtPct(trend.pct) })} — ${fe(locale, "search_change_caption")}`;
  return (
    <span className="fe-trend" title={fe(locale, "search_change_caption")}>
      <svg viewBox={`0 0 ${W} ${H}`} className="fe-spark" role="img" aria-label={label}>
        <path d={path(xs, ys)} fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinejoin="round" strokeLinecap="round" />
        <circle cx={xs.at(-1)} cy={ys.at(-1)} r="3" fill="currentColor" />
      </svg>
      {trend.pct !== null && <span>{fmtPct(trend.pct)}</span>}
    </span>
  );
}

const avg = (xs: number[]) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0);

/** 나이대별 검색 관심 — 나이대마다 작은 선 하나, 같은 가로축. 표로도 볼 수 있다. */
export function AgeCurves({ curves, locale, onDark = false }: { curves: GenerationCurve[]; locale: Locale; onDark?: boolean }) {
  const gens = L(locale).generation;
  const series = curves.filter((c) => c.points.length > 1).sort((a, b) => ORDER.indexOf(a.generation) - ORDER.indexOf(b.generation));
  if (!series.length) return <p className="fe-ages__empty">{fe(locale, "e_ages_none")}</p>;
  const dates = [...new Set(series.flatMap((c) => c.points.map((p) => p[0])))].sort();
  const W = 240, H = 36, pad = 3;
  const x = (d: string) => pad + (dates.indexOf(d) / Math.max(1, dates.length - 1)) * (W - pad * 2);
  const y = (v: number) => pad + (1 - Math.min(100, v) / 100) * (H - pad * 2);
  const gen = (g: string) => gens[g as keyof typeof gens] ?? g;
  return (
    <figure className={onDark ? "fe-ages fe-ages--dark" : "fe-ages"}>
      <ul className="fe-ages__list">
        {series.map((c) => {
          const pts = [...c.points].sort((a, b) => a[0].localeCompare(b[0]));
          return (
            <li key={c.generation} className="fe-ages__row">
              <span className="fe-ages__gen">{gen(c.generation)}</span>
              <svg viewBox={`0 0 ${W} ${H}`} className="fe-ages__svg" preserveAspectRatio="none" aria-hidden>
                <line x1={pad} x2={W - pad} y1={H - pad} y2={H - pad} className="fe-ages__baseline" strokeWidth="1" />
                <path d={path(pts.map((p) => x(p[0])), pts.map((p) => y(p[1])))} fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
              </svg>
              <span className="fe-ages__peak">{c.peak_date ? fe(locale, "peak", { date: ym(c.peak_date) }) : ""}</span>
            </li>
          );
        })}
      </ul>
      <figcaption className="fe-ages__cap">{dates.length > 1 && <span>{ym(dates[0])}–{ym(dates[dates.length - 1])}. </span>}{fe(locale, "e_ages_note")}</figcaption>
      <details className="fe-ages__table">
        <summary>{fe(locale, "table_view")}</summary>
        <table>
          <thead><tr><th scope="col">{fe(locale, "gen_col")}</th><th scope="col">{fe(locale, "latest_col")}</th><th scope="col">{fe(locale, "prev_col")}</th><th scope="col">{fe(locale, "peak_col")}</th></tr></thead>
          <tbody>
            {series.map((c) => {
              const v = [...c.points].sort((a, b) => a[0].localeCompare(b[0])).map((p) => p[1]);
              return (
                <tr key={c.generation}>
                  <th scope="row">{gen(c.generation)}</th>
                  <td>{avg(v.slice(-28)).toFixed(1)}</td>
                  <td>{v.length >= 56 ? avg(v.slice(-56, -28)).toFixed(1) : "—"}</td>
                  <td>{c.peak_date ? ym(c.peak_date) : "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </details>
    </figure>
  );
}
