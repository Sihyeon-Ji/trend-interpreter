import { t, type Locale } from "@/lib/i18n";
import { fmtDate, fmtInt } from "@/lib/labels";
import type { WeeklyPoint } from "@/lib/types";

const WEEK_MS = 7 * 86400000;

/** 마지막 주가 아직 끝나지 않았나 (월요일 시작 + 7일이 지금보다 뒤). */
export function isPartialWeek(p: WeeklyPoint | undefined, now = Date.now()): boolean {
  return !!p && new Date(p.week_start).getTime() + WEEK_MS > now;
}

/* 사전 항목의 주별 언급 선 — 끝난 주는 실선, 아직 모으는 이번 주는 점선. 눈금 글자는 SVG 밖 HTML 로 두어
   휴대폰에서 작아지지 않게 하고, 면을 칠하지 않는다. 화면 읽기 프로그램에는 같은 수를 표로 준다. */
export function TrendChart({ points, locale, partial }: { points: WeeklyPoint[]; locale: Locale; partial: boolean }) {
  if (points.length < 2) return null;
  const W = 480, H = 96, pad = 4;
  const max = Math.max(1, ...points.map((p) => p.count));
  const x = (i: number) => pad + (i / (points.length - 1)) * (W - pad * 2);
  const y = (v: number) => pad + (H - pad * 2) * (1 - v / max);
  const path = (ps: WeeklyPoint[], from: number) => ps.map((p, i) => `${i ? "L" : "M"}${x(from + i).toFixed(1)},${y(p.count).toFixed(1)}`).join(" ");
  const done = partial ? points.slice(0, -1) : points;
  const last = points.length - 1;
  return (
    <figure className="max-w-[560px] space-y-1">
      <p className="text-[12px] tabular-nums text-steel">{t(locale, "term_chart_max").replace("{n}", fmtInt(Math.max(0, ...points.map((p) => p.count))))}</p>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="block h-24 w-full text-ink" aria-hidden>
        <line x1={pad} x2={W - pad} y1={H - pad} y2={H - pad} className="stroke-hairline" strokeWidth="1" vectorEffect="non-scaling-stroke" />
        <path d={path(done, 0)} fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
        {partial && (
          <path d={path(points.slice(-2), last - 1)} fill="none" stroke="currentColor" strokeWidth="1.5" strokeDasharray="4 4" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
        )}
      </svg>
      <div className="flex justify-between gap-4 text-[12px] tabular-nums text-steel">
        <span>{fmtDate(points[0].week_start)}</span>
        <span>{fmtDate(points[last].week_start)}</span>
      </div>
      {partial && <figcaption className="text-[13px] text-steel">{t(locale, "term_week_partial")}</figcaption>}
      <table className="sr-only">
        <caption>{t(locale, "term_chart_caption")}</caption>
        <thead><tr><th scope="col">{t(locale, "term_col_week")}</th><th scope="col">{t(locale, "term_col_count")}</th></tr></thead>
        <tbody>{points.map((p) => <tr key={p.week_start}><td>{fmtDate(p.week_start)}</td><td>{p.count}</td></tr>)}</tbody>
      </table>
    </figure>
  );
}
