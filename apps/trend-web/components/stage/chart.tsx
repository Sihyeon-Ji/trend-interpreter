"use client";

import { useId, useState } from "react";
import type { Locale } from "@/lib/i18n";
import type { WeeklyPoint } from "@/lib/types";
import { fmtDay, fmtN } from "./bits";
import { tx } from "./copy";

/* 12주 언급 — 한 계열이라 범례 없이 제목이 계열을 말한다. 선 2px, 면은 같은 색 10%, 눈금은 가는 실선.
   가로 위치를 따라가는 세로 선이 가장 가까운 주를 잡고(마우스·키보드 같게), 값은 굵게 먼저. 표로도 읽힌다. */
export function TrendChart({ weekly, locale, partial = false, height = 120 }: { weekly: WeeklyPoint[]; locale: Locale; partial?: boolean; height?: number }) {
  const [at, setAt] = useState<number | null>(null);
  const id = useId();
  const pts = weekly.slice(-12);
  if (pts.length < 2) return null;
  const W = 600, H = height, top = 10, bottom = 4;
  const max = Math.max(1, ...pts.map((p) => p.count));
  const nice = niceMax(max);
  const x = (i: number) => (i / (pts.length - 1)) * W;
  const y = (v: number) => top + (1 - v / nice) * (H - top - bottom);
  const full = partial ? pts.slice(0, -1) : pts;
  const line = full.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.count).toFixed(1)}`).join("");
  const area = `${line}L${x(full.length - 1).toFixed(1)},${H - bottom}L0,${H - bottom}Z`;
  const tail = partial ? `M${x(pts.length - 2).toFixed(1)},${y(pts[pts.length - 2].count).toFixed(1)}L${x(pts.length - 1).toFixed(1)},${y(pts[pts.length - 1].count).toFixed(1)}` : "";
  const peak = pts.reduce((b, p, i) => (p.count > pts[b].count ? i : b), 0);
  const cur = at ?? null;
  const pick = (clientX: number, el: Element) => {
    const r = el.getBoundingClientRect();
    const i = Math.round(((clientX - r.left) / r.width) * (pts.length - 1));
    setAt(Math.max(0, Math.min(pts.length - 1, i)));
  };
  return (
    <figure className="rs-chart" style={{ "--rs-chart-h": `${H}px` } as React.CSSProperties}>
      <div
        className="rs-chart-plot"
        role="img"
        tabIndex={0}
        aria-label={tx(locale, "chart_label", { max: fmtN(pts[peak].count) })}
        aria-describedby={`${id}-t`}
        onPointerMove={(e) => pick(e.clientX, e.currentTarget)}
        onPointerLeave={() => setAt(null)}
        onFocus={() => setAt(pts.length - 1)}
        onBlur={() => setAt(null)}
        onKeyDown={(e) => {
          if (e.key === "ArrowLeft") { e.preventDefault(); setAt((a) => Math.max(0, (a ?? pts.length - 1) - 1)); }
          if (e.key === "ArrowRight") { e.preventDefault(); setAt((a) => Math.min(pts.length - 1, (a ?? 0) + 1)); }
        }}
      >
        <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" aria-hidden="true">
          <line className="rs-chart-grid" x1="0" x2={W} y1={y(nice)} y2={y(nice)} />
          <line className="rs-chart-grid" x1="0" x2={W} y1={y(nice / 2)} y2={y(nice / 2)} />
          <line className="rs-chart-base" x1="0" x2={W} y1={H - bottom} y2={H - bottom} />
          <path className="rs-chart-area" d={area} />
          <path className="rs-chart-line" d={line} />
          {tail ? <path className="rs-chart-tail" d={tail} /> : null}
          {cur != null ? <line className="rs-chart-cross" x1={x(cur)} x2={x(cur)} y1={top - 6} y2={H - bottom} /> : null}
        </svg>
        <span className="rs-chart-y rs-num" aria-hidden="true">{tx(locale, "chart_times", { n: fmtN(nice) })}</span>
        <span className="rs-chart-dot" style={{ left: `${(x(cur ?? peak) / W) * 100}%`, top: `${y(pts[cur ?? peak].count)}px` }} aria-hidden="true" />
        {cur != null ? (
          <span className="rs-chart-tip" style={{ left: `${(x(cur) / W) * 100}%` }} data-edge={cur < 2 ? "start" : cur > pts.length - 3 ? "end" : undefined} role="status">
            <b className="rs-num">{tx(locale, "chart_times", { n: fmtN(pts[cur].count) })}</b>
            <span>{tx(locale, "chart_week", { date: fmtDay(pts[cur].week_start, locale) })}</span>
          </span>
        ) : null}
      </div>
      <div className="rs-chart-axis" aria-hidden="true">
        <span>{fmtDay(pts[0].week_start, locale)}</span>
        <span>{fmtDay(pts[pts.length - 1].week_start, locale)}</span>
      </div>
      <table className="rs-sr" id={`${id}-t`}>
        <caption>{tx(locale, "xp_trend")}</caption>
        <tbody>{pts.map((p) => <tr key={p.week_start}><th scope="row">{fmtDay(p.week_start, locale)}</th><td>{p.count}</td></tr>)}</tbody>
      </table>
    </figure>
  );
}

function niceMax(v: number) {
  if (v <= 5) return 5;
  const p = 10 ** Math.floor(Math.log10(v));
  const n = v / p;
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * p;
}

/** 목록 한 줄의 작은 선 — 숫자는 옆 칸이 말한다(화면 읽기에서는 숨김) */
export function Spark({ weekly, w = 72, h = 22 }: { weekly: WeeklyPoint[]; w?: number; h?: number }) {
  const pts = weekly.slice(-12);
  if (pts.length < 2) return <svg className="rs-spark" width={w} height={h} aria-hidden="true" />;
  const max = Math.max(1, ...pts.map((p) => p.count));
  const d = pts.map((p, i) => `${i ? "L" : "M"}${((i / (pts.length - 1)) * (w - 4) + 2).toFixed(1)},${(h - 3 - (p.count / max) * (h - 6)).toFixed(1)}`).join("");
  const last = pts[pts.length - 1];
  return (
    <svg className="rs-spark" width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden="true">
      <path d={d} />
      <circle cx={w - 2} cy={h - 3 - (last.count / max) * (h - 6)} r="2.5" />
    </svg>
  );
}
