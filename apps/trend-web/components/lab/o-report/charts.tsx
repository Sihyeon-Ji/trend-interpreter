/* 손으로 그린 SVG 그래프. 규칙 하나: 청록은 '최근 기간', 짙은 회색은 '그와 견준 직전 기간', 옅은 회색은 그 앞의 배경이다.
   숫자를 읽는 곳은 HTML 글자로 두고(SVG 글자는 휴대폰에서 작아진다), 그림은 모양만 맡는다. */
import type { Silhouette as Shape } from "@/lib/lab/o-report";

const pts = (values: number[], w: number, h: number, pad = 2) => {
  const max = Math.max(...values, 1e-6);
  const step = values.length > 1 ? (w - pad * 2) / (values.length - 1) : 0;
  return values.map((v, i) => [pad + i * step, pad + (1 - v / max) * (h - pad * 2)] as const);
};
const line = (p: readonly (readonly [number, number])[]) => p.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join("");

/** 표의 작은 추이 — 주 단위. 끝의 recent 주는 청록 */
export function Sparkline({ values, recent, className = "" }: { values: number[]; recent: number; className?: string }) {
  if (values.length < 2) return null;
  const W = 120, H = 32;
  const p = pts(values, W, H, 3);
  const cut = Math.max(0, p.length - recent - 1);
  const last = p[p.length - 1];
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className={`block h-8 w-[120px] ${className}`} aria-hidden focusable="false">
      <path d={line(p.slice(0, cut + 1))} fill="none" stroke="var(--or-line-strong)" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
      <path d={line(p.slice(cut))} fill="none" stroke="var(--or-petrol)" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={last[0]} cy={last[1]} r="2.4" fill="var(--or-petrol)" />
    </svg>
  );
}

/** 표지의 산등성이 — 곡선이 표지 아래에서 솟는다. 세 구간을 면으로 칠한다 */
export function SilhouetteShape({ shape, delay = 0 }: { shape: Shape; delay?: number }) {
  const n = shape.values.length;
  if (n < 3) return null;
  const W = n - 1, H = 100;
  const max = Math.max(...shape.values, 1e-6);
  const y = (v: number) => H - (v / max) * (H - 6);
  const area = (from: number, to: number) => {
    const xs = Array.from({ length: to - from + 1 }, (_, i) => from + i);
    return `M${from},${H} ${xs.map((x) => `L${x},${y(shape.values[x]).toFixed(2)}`).join(" ")} L${to},${H} Z`;
  };
  const recentFrom = Math.max(0, n - 1 - shape.recent);
  const baseFrom = Math.max(0, recentFrom - shape.base);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" aria-hidden focusable="false">
      <g className="or-rise" style={{ animationDelay: `${delay}ms` }}>
        {baseFrom > 0 && <path d={area(0, baseFrom)} fill="var(--or-context)" />}
        <path d={area(baseFrom, recentFrom)} fill="var(--or-base)" />
        <path d={area(recentFrom, n - 1)} fill="var(--or-petrol)" />
      </g>
    </svg>
  );
}

/** 미리보기의 추이 — 주 단위, 가로로 넓게. 최근 창 뒤에 옅은 청록 띠 */
export function WeeklyBars({ values, recent, height = 64 }: { values: number[]; recent: number; height?: number }) {
  if (values.length < 2) return null;
  const n = values.length;
  const W = n * 10, H = height;
  const max = Math.max(...values, 1e-6);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="block w-full" style={{ height }} aria-hidden focusable="false">
      {values.map((v, i) => {
        const h = Math.max(1.5, (v / max) * (H - 4));
        const tone = i >= n - recent ? "var(--or-petrol)" : i >= n - recent * 2 ? "var(--or-base)" : "var(--or-context)";
        return <rect key={i} x={i * 10 + 1.5} y={H - h} width="7" height={h} fill={tone} />;
      })}
    </svg>
  );
}
