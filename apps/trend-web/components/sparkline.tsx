import type { WeeklyPoint } from "@/lib/types";

/* 무채색 스파크라인. 항목 페이지와 관리 화면에서만 쓴다. */
export function Sparkline({ points, width = 240, height = 48, className, label }: { points: WeeklyPoint[]; width?: number; height?: number; className?: string; label?: string }) {
  const pad = 4;
  const values = points.map((p) => p.count);
  const max = Math.max(1, ...values);
  const stepX = (width - pad * 2) / Math.max(1, values.length - 1);
  const y = (v: number) => pad + (height - pad * 2) * (1 - v / max);
  const coords = values.map((v, i) => [pad + i * stepX, y(v)] as const);
  const line = coords.map(([x, yy], i) => `${i ? "L" : "M"}${x.toFixed(1)},${yy.toFixed(1)}`).join(" ");
  const area = `${line} L${coords.at(-1)![0].toFixed(1)},${height - pad} L${pad},${height - pad} Z`;
  const [ex, ey] = coords.at(-1)!;
  return (
    <svg viewBox={`0 0 ${width} ${height}`} width={width} height={height} className={`text-charcoal ${className ?? ""}`}
      {...(label ? { role: "img", "aria-label": label } : { "aria-hidden": true })}>
      <line x1={pad} x2={width - pad} y1={height - pad} y2={height - pad} className="stroke-hairline" strokeWidth="1" />
      <path d={area} fill="currentColor" opacity="0.07" />
      <path d={line} fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={ex} cy={ey} r="3" fill="currentColor" stroke="#ffffff" strokeWidth="1.5" />
    </svg>
  );
}
