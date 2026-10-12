"use client";

import { useMemo, useRef, useState } from "react";
import type { LabLocale as Locale } from "@/lib/i18n";
import { fe } from "@/lib/lab/f-editorial/copy";
import { ageChange, fmtPct, type AgeChange } from "@/lib/lab/f-editorial";
import { L, fmtDate } from "@/lib/labels";
import type { GenerationCurve } from "@/lib/trends/types";

/* 나이대별 검색 관심 — 나이대마다 작은 선 하나, 같은 달력 가로축(없는 날은 잇지 않는다). 십자선 하나가 모든 나이대를 같은 날로 읽는다:
   마우스를 옮기거나(←→, Shift 는 7일) 화살표 키로. 오른쪽 값은 평소엔 최근 4주 대 이전 4주의 변화, 날짜를 고르면 그날의 값.
   같은 값을 표로도 연다. 선은 한 색(코발트, 표지에서는 흰색). */
const ORDER = ["10s", "20s", "30s", "40s", "50s+"];
const DAY = 86_400_000;
const W = 240, H = 36, PAD = 3;
const dayMs = (d: string) => Date.parse(`${d.slice(0, 10)}T00:00:00Z`);
const iso = (t: number) => new Date(t).toISOString().slice(0, 10);
const ym = (d: string) => d.slice(0, 7).replace("-", ".");

/** 날짜순 점을 선으로. 사흘 넘게 빈 곳은 잇지 않는다 — 없는 날을 이어 그리면 없던 추이가 생긴다. */
function linePath(points: [string, number][], x: (d: string) => number, y: (v: number) => number): string {
  let d = "";
  let prev: number | null = null;
  for (const [day, v] of points) {
    const t = dayMs(day);
    d += `${prev !== null && t - prev <= 3 * DAY ? "L" : "M"}${x(day).toFixed(1)},${y(v).toFixed(1)}`;
    prev = t;
  }
  return d;
}

export function AgeCurves({ curves, locale, onDark = false }: { curves: GenerationCurve[]; locale: Locale; onDark?: boolean }) {
  const gens = L(locale).generation;
  const gen = (g: string) => gens[g as keyof typeof gens] ?? g;
  const series = useMemo<AgeChange[]>(
    () => curves.filter((c) => c.points.length > 1).map(ageChange).sort((a, b) => ORDER.indexOf(a.generation) - ORDER.indexOf(b.generation)),
    [curves],
  );
  const maps = useMemo(() => series.map((s) => new Map(s.points.map(([d, v]) => [d.slice(0, 10), v]))), [series]);
  const plot = useRef<SVGSVGElement>(null);
  const [at, setAt] = useState<string | null>(null);
  if (!series.length) return <p className="fe-ages__empty">{fe(locale, "e_ages_none")}</p>;

  const from = series.map((s) => s.points[0][0]).sort()[0];
  const to = series.map((s) => s.end).filter((d): d is string => !!d).sort().at(-1) ?? from;
  const span = Math.max(1, dayMs(to) - dayMs(from));
  const x = (d: string) => PAD + ((dayMs(d) - dayMs(from)) / span) * (W - PAD * 2);
  const y = (v: number) => PAD + (1 - Math.min(100, Math.max(0, v)) / 100) * (H - PAD * 2);

  const pick = (clientX: number) => {
    const r = plot.current?.getBoundingClientRect();
    if (!r || r.width <= 0) return;
    const ratio = Math.min(1, Math.max(0, (clientX - r.left) / r.width));
    setAt(iso(dayMs(from) + Math.round((ratio * span) / DAY) * DAY));
  };
  const step = (days: number) => {
    const base = at ? dayMs(at) : dayMs(to);
    setAt(iso(Math.min(dayMs(to), Math.max(dayMs(from), base + days * DAY))));
  };
  const valueAt = (i: number) => (at && maps[i].has(at) ? String(Math.round(maps[i].get(at)!)) : "—");
  const readout = at ? fe(locale, "ages_read", { date: fmtDate(at), values: series.map((s, i) => `${gen(s.generation)} ${valueAt(i)}`).join(", ") }) : fe(locale, "ages_hint");

  return (
    <figure className={onDark ? "fe-ages fe-ages--dark" : "fe-ages"}>
      <div
        className="fe-ages__plot"
        role="group"
        tabIndex={0}
        aria-label={`${fe(locale, "e_ages")}. ${fe(locale, "ages_hint")}`}
        onPointerMove={(e) => pick(e.clientX)}
        onPointerLeave={() => setAt(null)}
        onBlur={() => setAt(null)}
        onKeyDown={(e) => {
          if (e.key === "ArrowLeft" || e.key === "ArrowRight") { e.preventDefault(); step((e.key === "ArrowLeft" ? -1 : 1) * (e.shiftKey ? 7 : 1)); }
          else if (e.key === "Escape") setAt(null);
        }}
      >
        <ul className="fe-ages__list">
          {series.map((s, i) => (
            <li key={s.generation} className="fe-ages__row">
              <span className="fe-ages__gen">{gen(s.generation)}</span>
              <svg ref={i === 0 ? plot : undefined} viewBox={`0 0 ${W} ${H}`} className="fe-ages__svg" preserveAspectRatio="none" aria-hidden>
                <line x1={PAD} x2={W - PAD} y1={H - PAD} y2={H - PAD} className="fe-ages__baseline" strokeWidth="1" vectorEffect="non-scaling-stroke" />
                <path d={linePath(s.points, x, y)} fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
                {at && <line x1={x(at)} x2={x(at)} y1={0} y2={H} className="fe-ages__cursor" strokeWidth="1" vectorEffect="non-scaling-stroke" />}
              </svg>
              <span className="fe-ages__val">{at ? valueAt(i) : s.change !== null ? fmtPct(s.change) : <span className="fe-ages__thin">{fe(locale, "thin")}</span>}</span>
            </li>
          ))}
        </ul>
        <p className="fe-ages__read" aria-live="polite">{readout}</p>
      </div>
      <figcaption className="fe-ages__cap">{ym(from)}–{ym(to)}. {fe(locale, "e_ages_note")} {fe(locale, "search_change_caption")}.</figcaption>
      <details className="fe-ages__table">
        <summary>{fe(locale, "table_view")}</summary>
        <table>
          <thead>
            <tr>
              <th scope="col">{fe(locale, "gen_col")}</th>
              <th scope="col">{fe(locale, "latest_col")}</th>
              <th scope="col">{fe(locale, "prev_col")}</th>
              <th scope="col">{fe(locale, "change_col")}</th>
              <th scope="col">{fe(locale, "peak_col")}</th>
            </tr>
          </thead>
          <tbody>
            {series.map((s) => (
              <tr key={s.generation}>
                <th scope="row">{gen(s.generation)}</th>
                <td>{s.latest.toFixed(1)}</td>
                <td>{s.previous.toFixed(1)}</td>
                <td>{s.change !== null ? fmtPct(s.change) : fe(locale, "thin")}</td>
                <td>{s.peak ? ym(s.peak) : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}
