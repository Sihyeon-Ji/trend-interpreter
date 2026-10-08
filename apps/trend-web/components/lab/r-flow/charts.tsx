/* 작은 그림 둘 — 12주 선(목록 한 줄)과 주간 막대(밈 항목). 값은 백엔드가 센 주간 언급 수 그대로, 꾸밈 없이. */
import type { WeeklyPoint } from "@/lib/types";

export function Spark({ values, w = 84, h = 22, label }: { values: number[]; w?: number; h?: number; label: string }) {
  if (values.length < 2) return <span className="rf-muted" aria-label={label}>–</span>;
  const max = Math.max(1, ...values);
  const step = w / (values.length - 1);
  const y = (v: number) => h - 2 - (v / max) * (h - 4);
  const pts = values.map((v, i) => `${(i * step).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const last = values.length - 1;
  return (
    <svg className="rf-spark" width={w} height={h} viewBox={`0 0 ${w} ${h}`} role="img" aria-label={label}>
      <line x1="0" x2={w} y1={h - 1.5} y2={h - 1.5} />
      <polyline points={pts} />
      <circle cx={last * step} cy={y(values[last])} r="2.2" />
    </svg>
  );
}

const md = (iso: string) => iso.slice(5, 10).replace("-", ".");

/** 주간 막대 12개. 이번 주가 아직 끝나지 않았으면 옅게(덜 센 주를 줄어든 것처럼 보이지 않게) */
export function WeekBars({ points, partial, label }: { points: WeeklyPoint[]; partial: boolean; label: string }) {
  const W = 560, H = 132, top = 18, base = 108;
  const n = points.length;
  if (!n) return null;
  const max = Math.max(1, ...points.map((p) => p.count));
  const gap = 6;
  const bw = (W - gap * (n - 1)) / n;
  const peak = points.reduce((a, p, i) => (p.count > points[a].count ? i : a), 0);
  return (
    <svg className="rf-bars" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label}>
      <line x1="0" x2={W} y1={base + 0.5} y2={base + 0.5} />
      {points.map((p, i) => {
        const hgt = p.count ? Math.max(3, ((base - top) * p.count) / max) : 2;
        const k = i === n - 1 && partial ? "partial" : p.count ? "bar" : "zero";
        return (
          <g key={p.week_start}>
            <rect data-k={k} x={i * (bw + gap)} y={base - hgt} width={bw} height={hgt} rx="2">
              <title>{`${md(p.week_start)}: ${p.count}`}</title>
            </rect>
            {i === peak && p.count > 0 && <text x={i * (bw + gap) + bw / 2} y={base - hgt - 5} textAnchor="middle">{p.count}</text>}
          </g>
        );
      })}
      <text x="0" y={H - 6}>{md(points[0].week_start)}</text>
      <text x={W} y={H - 6} textAnchor="end">{md(points[n - 1].week_start)}</text>
    </svg>
  );
}
