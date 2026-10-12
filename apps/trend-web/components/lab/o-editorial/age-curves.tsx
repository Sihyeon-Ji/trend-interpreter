"use client";

import { useId, useMemo, useRef, useState } from "react";
import type { LabLocale as Locale } from "@/lib/i18n";
import { ageName, copy, curvePaths, fmtDay, pct, xOf, type AgeTrend } from "@/lib/lab/o-editorial";

const W = 1000;
const H = 44;
const DAY = 86_400_000;
const iso = (t: number) => new Date(t).toISOString().slice(0, 10);

/** 나이대별 네이버 검색 관심 — 작은 그림 여러 개(나이대마다 제 최고치 = 100). 한 줄의 십자선이 모든 나이대를 같은 날로 읽는다.
 *  값은 마우스·키보드(←→, Shift 는 7일)로 읽고, 같은 값을 표(달마다 평균)로도 연다. */
export function AgeCurves({ locale, ages }: { locale: Locale; ages: AgeTrend[] }) {
  const c = copy(locale);
  const id = useId();
  const box = useRef<HTMLDivElement>(null);
  const plot = useRef<HTMLDivElement>(null);
  const [at, setAt] = useState<string | null>(null);

  const from = useMemo(() => ages.map((a) => a.points[0]?.[0]).filter(Boolean).sort()[0] ?? "", [ages]);
  const to = useMemo(() => ages.map((a) => a.end).filter((d): d is string => !!d).sort().at(-1) ?? "", [ages]);
  const maps = useMemo(() => ages.map((a) => new Map(a.points.map(([d, v]) => [d.slice(0, 10), v]))), [ages]);
  const months = useMemo(() => {
    if (!from || !to) return [] as string[];
    const out: string[] = [];
    const d = new Date(`${from}T00:00:00Z`);
    d.setUTCDate(1);
    d.setUTCMonth(d.getUTCMonth() + 1);
    while (iso(d.getTime()) <= to) { out.push(iso(d.getTime())); d.setUTCMonth(d.getUTCMonth() + 1); }
    return out;
  }, [from, to]);
  const table = useMemo(() => {
    const rows = new Map<string, { sum: number[]; n: number[] }>();
    ages.forEach((a, i) => {
      for (const [d, v] of a.points) {
        const m = d.slice(0, 7);
        const r = rows.get(m) ?? { sum: ages.map(() => 0), n: ages.map(() => 0) };
        r.sum[i] += v; r.n[i] += 1;
        rows.set(m, r);
      }
    });
    return [...rows].sort((x, y) => x[0].localeCompare(y[0]));
  }, [ages]);

  if (!from || !to) return null;
  const span = Date.parse(`${to}T00:00:00Z`) - Date.parse(`${from}T00:00:00Z`);

  const pick = (clientX: number) => {
    const r = plot.current?.getBoundingClientRect();
    if (!r || r.width <= 0) return;
    const ratio = Math.min(1, Math.max(0, (clientX - r.left) / r.width));
    setAt(iso(Date.parse(`${from}T00:00:00Z`) + Math.round((ratio * span) / DAY) * DAY));
  };
  const step = (days: number) => {
    const base = at ? Date.parse(`${at}T00:00:00Z`) : Date.parse(`${to}T00:00:00Z`);
    const next = Math.min(Date.parse(`${to}T00:00:00Z`), Math.max(Date.parse(`${from}T00:00:00Z`), base + days * DAY));
    setAt(iso(next));
  };
  const x = at ? (xOf(at, from, to, W) / W) * 100 : null;
  const tipLeft = x === null ? 0 : x;

  return (
    <div>
      <div
        ref={box}
        className="oe-multiples"
        role="group"
        tabIndex={0}
        aria-label={`${c.secSearch}. ${c.searchKeys}`}
        aria-describedby={`${id}-read`}
        onPointerMove={(e) => pick(e.clientX)}
        onPointerLeave={() => setAt(null)}
        onKeyDown={(e) => {
          if (e.key === "ArrowLeft" || e.key === "ArrowRight") { e.preventDefault(); step((e.key === "ArrowLeft" ? -1 : 1) * (e.shiftKey ? 7 : 1)); }
          else if (e.key === "Escape") setAt(null);
        }}
        onBlur={() => setAt(null)}
      >
        {ages.map((a, i) => {
          const { line, area } = curvePaths(a.points, from, to, W, H);
          const winFrom = a.end ? iso(Date.parse(`${a.end}T00:00:00Z`) - 27 * DAY) : null;
          const wx = winFrom && a.end ? xOf(winFrom, from, to, W) : null;
          return (
            <div key={a.gen} className="oe-multiple">
              <span className="oe-multiple-age">{ageName(locale, a.gen)}</span>
              <div ref={i === 0 ? plot : undefined} style={{ position: "relative" }}>
                <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" aria-hidden>
                  {wx !== null && a.change !== null && <rect x={wx} y={0} width={Math.max(0, xOf(a.end!, from, to, W) - wx)} height={H} fill="var(--oe-tint)" />}
                  <line x1={0} x2={W} y1={H - 0.5} y2={H - 0.5} stroke="var(--oe-line)" strokeWidth={1} vectorEffect="non-scaling-stroke" />
                  <path d={area} fill="var(--oe-blue)" fillOpacity={0.1} />
                  <path d={line} fill="none" stroke="var(--oe-blue)" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
                  {x !== null && <line x1={(x / 100) * W} x2={(x / 100) * W} y1={0} y2={H} stroke="var(--oe-ink)" strokeWidth={1} vectorEffect="non-scaling-stroke" />}
                </svg>
              </div>
              <span className="oe-multiple-val">{a.change === null ? <span className="oe-strip-thin">{a.state === "low" ? c.lowBase : c.thin}</span> : pct(a.change)}</span>
            </div>
          );
        })}
        <div className="oe-multiple-axis" aria-hidden>
          <span />
          <div style={{ position: "relative", height: 18 }}>
            {months.map((m) => (
              <span key={m} className="oe-meta" style={{ position: "absolute", left: `${(xOf(m, from, to, W) / W) * 100}%`, transform: "translateX(-50%)", whiteSpace: "nowrap" }}>
                {locale === "ko" ? `${Number(m.slice(5, 7))}월` : new Intl.DateTimeFormat("en-US", { month: "short", timeZone: "UTC" }).format(new Date(`${m}T00:00:00Z`))}
              </span>
            ))}
          </div>
          <span className="oe-meta" style={{ textAlign: "right" }}>{c.changeLabel}</span>
        </div>
        {at && x !== null && (
          <div className="oe-tip" style={{ top: 0, left: `calc(72px + 12px + (100% - 72px - 64px - 24px) * ${tipLeft / 100})`, transform: `translateX(${tipLeft > 60 ? "calc(-100% - 12px)" : "12px"})` }}>
            <strong className="oe-num">{fmtDay(locale, at)}</strong>
            <table style={{ marginTop: 4, borderCollapse: "collapse" }}>
              <tbody>
                {ages.map((a, i) => {
                  const v = maps[i].get(at);
                  return (
                    <tr key={a.gen}>
                      <td className="oe-num" style={{ paddingRight: 10, fontWeight: 700, textAlign: "right" }}>{v === undefined ? "—" : Math.round(v)}</td>
                      <td>{ageName(locale, a.gen)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        <p id={`${id}-read`} className="oe-sr" aria-live="polite">
          {at ? `${fmtDay(locale, at)}: ${ages.map((a, i) => `${ageName(locale, a.gen)} ${maps[i].has(at) ? Math.round(maps[i].get(at)!) : "—"}`).join(", ")}` : ""}
        </p>
      </div>
      <details className="oe-details" style={{ marginTop: 14 }}>
        <summary>{c.searchTable}</summary>
        <div style={{ overflowX: "auto" }}>
          <table className="oe-table">
            <thead>
              <tr>
                <th scope="col">{c.monthCol}</th>
                {ages.map((a) => <th key={a.gen} scope="col" style={{ textAlign: "right" }}>{ageName(locale, a.gen)}</th>)}
              </tr>
            </thead>
            <tbody>
              {table.map(([m, r]) => (
                <tr key={m}>
                  <th scope="row" className="oe-num" style={{ fontWeight: 500, color: "var(--oe-ink)", borderBottom: "1px solid var(--oe-line)" }}>{m.replace("-", ".")}</th>
                  {r.sum.map((s, i) => <td key={i} className="oe-num" style={{ textAlign: "right" }}>{r.n[i] ? Math.round(s / r.n[i]) : "—"}</td>)}
                </tr>
              ))}
              <tr>
                <th scope="row" style={{ fontWeight: 600, color: "var(--oe-ink)" }}>{c.peakLabel}</th>
                {ages.map((a) => <td key={a.gen} className="oe-num" style={{ textAlign: "right" }}>{a.peak ? fmtDay(locale, a.peak) : "—"}</td>)}
              </tr>
              <tr>
                <th scope="row" style={{ fontWeight: 600, color: "var(--oe-ink)" }}>{c.changeLabel}</th>
                {ages.map((a) => <td key={a.gen} className="oe-num" style={{ textAlign: "right" }}>{a.change === null ? (a.state === "low" ? c.lowBase : c.thin) : pct(a.change)}</td>)}
              </tr>
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
