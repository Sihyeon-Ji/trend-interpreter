import { t, type Locale } from "@/lib/i18n";
import { L } from "@/lib/labels";
import type { GenerationCurve } from "@/lib/trends/types";

/* 세대별 검색 관심 곡선 — 한 축, 얇은 선, 선 끝 직접 라벨. 색은 단색 단계 + 점선으로 구분(색만으로 구분하지 않는다). */
const STYLE: Record<string, { stroke: string; dash?: string; width: number }> = {
  "10s": { stroke: "#1a1a1a", width: 1.6 },
  "20s": { stroke: "#4b5563", width: 1.4 },
  "30s": { stroke: "#6b7280", width: 1.4, dash: "4 3" },
  "40s": { stroke: "#9aa1aa", width: 1.4 },
  "50s+": { stroke: "#9aa1aa", width: 1.4, dash: "2 3" },
};

export function GenerationCurves({ curves, locale }: { curves: GenerationCurve[]; locale: Locale }) {
  const labels = L(locale);
  const series = curves.filter((c) => c.points.length > 1);
  if (!series.length) return null;
  const W = 640, H = 220, padL = 8, padR = 72, padT = 12, padB = 26;
  const dates = Array.from(new Set(series.flatMap((c) => c.points.map((p) => p[0])))).sort();
  const x = (d: string) => padL + (dates.indexOf(d) / Math.max(1, dates.length - 1)) * (W - padL - padR);
  const y = (v: number) => padT + (1 - v / 100) * (H - padT - padB);
  const ticks = [dates[0], dates[Math.floor(dates.length / 2)], dates[dates.length - 1]];
  return (
    <figure>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full max-w-[640px] text-charcoal" role="img" aria-label={t(locale, "term_gen_curves")}>
        {[0, 50, 100].map((v) => <line key={v} x1={padL} x2={W - padR} y1={y(v)} y2={y(v)} stroke="#e6e8eb" strokeWidth={1} />)}
        {(() => {
          // 라벨 y 를 마지막 값 순으로 정렬해 12px 씩 벌린다
          const ends = series.map((c) => ({ c, y: y(c.points[c.points.length - 1][1]) })).sort((a, b) => a.y - b.y);
          for (let i = 1; i < ends.length; i++) if (ends[i].y - ends[i - 1].y < 12) ends[i].y = ends[i - 1].y + 12;
          const over = (ends.at(-1)?.y ?? 0) - (H - padB - 4);
          if (over > 0) for (const e of ends) e.y -= over;
          const labelY = new Map(ends.map((e) => [e.c.generation, e.y]));
          return series.map((c) => {
          const st = STYLE[c.generation] ?? STYLE["40s"];
          const d = c.points.map(([dt, v], i) => `${i ? "L" : "M"}${x(dt).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
          const last = c.points[c.points.length - 1];
          const peak = c.peak_date ? c.points.find((p) => p[0] === c.peak_date) : null;
          return (
            <g key={c.generation}>
              <path d={d} fill="none" stroke={st.stroke} strokeWidth={st.width} strokeDasharray={st.dash} />
              {peak && <circle cx={x(peak[0])} cy={y(peak[1])} r={3} fill={st.stroke} stroke="#fff" strokeWidth={1.5} />}
              <text x={x(last[0]) + 6} y={(labelY.get(c.generation) ?? y(last[1])) + 4} fontSize={11} fill={st.stroke}>{labels.generation[c.generation as keyof typeof labels.generation] ?? c.generation}</text>
            </g>
          );
          });
        })()}
        {ticks.map((d) => <text key={d} x={x(d)} y={H - 6} fontSize={11} fill="#6b7280" textAnchor={d === dates[0] ? "start" : d === dates[dates.length - 1] ? "end" : "middle"}>{d.replace(/^\d{4}-/, "").replace("-", ".")}</text>)}
      </svg>
      <figcaption className="mt-1 text-[12px] text-steel">
        {t(locale, "term_gen_curves_hint")}{" "}
        {series.filter((c) => c.peak_date).map((c) => `${labels.generation[c.generation as keyof typeof labels.generation] ?? c.generation} ${c.peak_date!.replace(/^\d{4}-/, "").replace("-", ".")}`).join(" · ")}
      </figcaption>
    </figure>
  );
}
