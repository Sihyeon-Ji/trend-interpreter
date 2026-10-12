import type { LabLocale as Locale } from "@/lib/i18n";
import { fe } from "@/lib/lab/f-editorial/copy";
import { fmtPct, type SearchTrend } from "@/lib/lab/f-editorial";
import { fmtDate } from "@/lib/labels";

/* 카드의 작은 추세선 — 전 나이대 평균의 주 평균, 0–100 고정 눈금에 바닥선(납작한 곡선을 요동치게 늘리지 않는다). 값(%)은 옆에 글자로.
   선은 한 색(코발트), 색으로 방향을 말하지 않는다. */
const path = (xs: number[], ys: number[]) => xs.map((x, i) => `${i ? "L" : "M"}${x.toFixed(1)},${ys[i].toFixed(1)}`).join(" ");

export function Sparkline({ trend, locale }: { trend: SearchTrend; locale: Locale }) {
  const W = 84, H = 26, pad = 3;
  const v = trend.weekly;
  if (v.length < 2) return null;
  const xs = v.map((_, i) => pad + (i / (v.length - 1)) * (W - pad * 2));
  const ys = v.map((y) => pad + (1 - Math.min(100, Math.max(0, y)) / 100) * (H - pad * 2));
  const value = trend.pct !== null ? fmtPct(trend.pct) : trend.stale && trend.end ? fe(locale, "search_until", { date: fmtDate(trend.end) }) : fe(locale, "search_thin");
  const label = trend.pct !== null ? `${fe(locale, "search_change", { pct: value })}, ${fe(locale, "search_change_caption")}` : value;
  return (
    <span className="fe-trend" title={fe(locale, "search_change_caption")}>
      <svg viewBox={`0 0 ${W} ${H}`} className="fe-spark" role="img" aria-label={label}>
        <line x1={pad} x2={W - pad} y1={H - pad} y2={H - pad} stroke="currentColor" strokeOpacity="0.3" strokeWidth="1" />
        <path d={path(xs, ys)} fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinejoin="round" strokeLinecap="round" />
        <circle cx={xs.at(-1)} cy={ys.at(-1)} r="3" fill="currentColor" />
      </svg>
      <span className={trend.pct !== null ? undefined : "fe-trend__thin"}>{value}</span>
    </span>
  );
}
