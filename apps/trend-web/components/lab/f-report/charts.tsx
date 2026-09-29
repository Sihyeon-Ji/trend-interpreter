/* 손으로 그린 SVG 차트. 글자는 HTML 에 두고(SVG 글자는 휴대폰에서 6px 까지 줄었다) 선만 SVG.
   가로로 늘어나는 차트는 preserveAspectRatio="none" + vector-effect 로 선 굵기를 지킨다. */
import type { Locale } from "@/lib/i18n";
import { c, genLabel } from "@/lib/lab/f-report-copy";
import { fmtMonth, type Trend } from "@/lib/lab/f-report";

function linePath(values: number[], W: number, H: number, pad: number, max: number) {
  const n = values.length;
  const x = (i: number) => pad + (n > 1 ? (i / (n - 1)) * (W - pad * 2) : (W - pad * 2) / 2);
  const y = (v: number) => pad + (1 - v / max) * (H - pad * 2);
  return { d: values.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" "), x, y };
}

/** 면이 있는 큰 곡선 — 주목 타일·항목 머리. 색은 currentColor. */
export function AreaCurve({ values, className, label }: { values: number[]; className?: string; label: string }) {
  if (values.length < 2) return null;
  const W = 300, H = 100, pad = 3;
  const max = Math.max(1, ...values);
  const { d } = linePath(values, W, H, pad, max);
  const area = `${d} L${W - pad},${H} L${pad},${H} Z`;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className={className} role="img" aria-label={label}>
      <path d={area} fill="currentColor" opacity="0.14" />
      <path d={d} fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

/** 목록의 작은 선. 고정 비율이라 끝점 동그라미가 찌그러지지 않는다. */
export function Sparkline({ values, className, label }: { values: number[]; className?: string; label: string }) {
  if (values.length < 2) return null;
  const W = 112, H = 30, pad = 3;
  const max = Math.max(1, ...values);
  const { d, x, y } = linePath(values, W, H, pad, max);
  const last = values.length - 1;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className={className} role="img" aria-label={label}>
      <line x1={pad} x2={W - pad} y1={H - pad} y2={H - pad} stroke="#e3e6e4" strokeWidth="1" />
      <path d={d} fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={x(last)} cy={y(values[last])} r="2.6" fill="currentColor" stroke="#fff" strokeWidth="1.2" />
    </svg>
  );
}

/** 나이대별 작은 곡선 다섯. 한 그림에 겹치지 않는다(옅은 선 둘이 구분되지 않았던 경험). 세로축은 0–100 공통. */
export function GenCurves({ byGen, locale, large }: { byGen: Trend["byGen"]; locale: Locale; large?: boolean }) {
  const series = byGen.filter((g) => g.spark.length > 1);
  if (!series.length) return null;
  const W = 100, H = 32, pad = 2;
  return (
    <ul className={`fr-gens${large ? " is-large" : ""}`}>
      {series.map((g) => {
        const { d } = linePath(g.spark, W, H, pad, 100);
        return (
          <li key={g.generation} className="fr-gen">
            <b>{genLabel(locale, g.generation)}</b>
            <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="fr-signal" role="img"
              aria-label={`${genLabel(locale, g.generation)}: ${c(locale, "interest")} ${g.spark.at(-1)}`}>
              <line x1={pad} x2={W - pad} y1={H - pad} y2={H - pad} stroke="#e3e6e4" strokeWidth="1" vectorEffect="non-scaling-stroke" />
              <path d={d} fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
            </svg>
            {g.peak && <span className="fr-num">{c(locale, "peak")} {fmtMonth(g.peak)}</span>}
          </li>
        );
      })}
    </ul>
  );
}

/** ▲38% / ▼8% / 변화 없음 — 글자만. 색은 부모 클래스(is-up / is-down)가 정한다. */
export function growthText(pct: number | null, locale: Locale): { text: string; dir: "up" | "down" | "flat" | "none" } {
  if (pct === null) return { text: c(locale, "no_curve_row"), dir: "none" };
  if (Math.abs(pct) < 1) return { text: c(locale, "flat"), dir: "flat" };
  return pct > 0 ? { text: `▲ ${pct}%`, dir: "up" } : { text: `▼ ${Math.abs(pct)}%`, dir: "down" };
}
