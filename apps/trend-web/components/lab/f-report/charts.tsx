/* 손으로 그린 SVG 차트. 글자는 HTML 에 두고(SVG 글자는 휴대폰에서 6px 까지 줄었다) 선만 SVG.
   가로로 늘어나는 차트는 preserveAspectRatio="none" + vector-effect 로 선 굵기를 지킨다.
   곡선은 두 톤이다 — 끝의 '최근 창' 은 진하게, 그 앞 '비교 창' 은 옅게, 더 앞은 회색. 그래서 곡선 자체가 무엇을 무엇과 견줬는지 말한다. */
import type { LabLocale as Locale } from "@/lib/i18n";
import { c, genLabel } from "@/lib/lab/f-report/copy";
import { fmtMonth, type GenTrend } from "@/lib/lab/f-report";

function scale(values: number[], W: number, H: number, pad: number, max: number) {
  const n = values.length;
  const x = (i: number) => pad + (n > 1 ? (i / (n - 1)) * (W - pad * 2) : (W - pad * 2) / 2);
  const y = (v: number) => pad + (1 - v / max) * (H - pad * 2);
  return { x, y };
}
const seg = (values: number[], from: number, to: number, x: (i: number) => number, y: (v: number) => number) =>
  values.slice(from, to + 1).map((v, k) => `${k ? "L" : "M"}${x(from + k).toFixed(1)},${y(v).toFixed(1)}`).join(" ");

/** 낱말이 딛고 선 땅 — 타일·항목 머리의 큰 곡선. 면은 바닥까지 닿고, 최근 창(recent 점)은 진한 신호색, 그 앞 비교 창(base 점)은 옅은 신호색, 더 앞은 회색. */
export function Ground({ values, recent, base, className, label }: { values: number[]; recent: number; base: number; className?: string; label: string }) {
  if (values.length < 2) return null;
  const W = 300, H = 100, pad = 0;
  const max = Math.max(1, ...values);
  const { x, y } = scale(values, W, H, pad, max);
  const n = values.length;
  const r0 = Math.max(0, n - recent), b0 = Math.max(0, r0 - base);
  const area = (from: number, to: number) => `${seg(values, from, to, x, y)} L${x(to).toFixed(1)},${H} L${x(from).toFixed(1)},${H} Z`;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className={className} role="img" aria-label={label}>
      {b0 > 0 && <path d={area(0, b0)} className="fr-g-old" />}
      {r0 > b0 && <path d={area(b0, r0)} className="fr-g-base" />}
      <path d={area(r0, n - 1)} className="fr-g-recent" />
      {b0 > 0 && <path d={seg(values, 0, b0, x, y)} className="fr-l-old" fill="none" vectorEffect="non-scaling-stroke" />}
      {r0 > b0 && <path d={seg(values, b0, r0, x, y)} className="fr-l-base" fill="none" vectorEffect="non-scaling-stroke" />}
      <path d={seg(values, r0, n - 1, x, y)} className="fr-l-recent" fill="none" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

/** 목록의 작은 선. 끝 recent 주는 진하게. 고정 비율이라 끝점 동그라미가 찌그러지지 않는다. */
export function Sparkline({ values, recent, className, label }: { values: number[]; recent: number; className?: string; label: string }) {
  if (values.length < 2) return null;
  const W = 112, H = 30, pad = 3;
  const max = Math.max(1, ...values);
  const { x, y } = scale(values, W, H, pad, max);
  const n = values.length, r0 = Math.max(0, n - recent);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className={className} role="img" aria-label={label}>
      <line x1={pad} x2={W - pad} y1={H - pad} y2={H - pad} className="fr-l-axis" />
      {r0 > 0 && <path d={seg(values, 0, r0, x, y)} className="fr-l-base" fill="none" />}
      <path d={seg(values, r0, n - 1, x, y)} className="fr-l-recent" fill="none" />
      <circle cx={x(n - 1)} cy={y(values[n - 1])} r="2.6" className="fr-dot" />
    </svg>
  );
}

/** 나이대별 작은 곡선 다섯. 한 그림에 겹치지 않는다(옅은 선 둘이 구분되지 않았던 경험). 세로축은 0–100 공통. 셀 수 없는 나이대는 회색으로. */
export function GenCurves({ byGen, locale, large }: { byGen: GenTrend[]; locale: Locale; large?: boolean }) {
  const series = byGen.filter((g) => g.spark.length > 1);
  if (!series.length) return null;
  const W = 100, H = 32, pad = 2;
  return (
    <ul className={`fr-gens${large ? " is-large" : ""}`}>
      {series.map((g) => {
        const { x, y } = scale(g.spark, W, H, pad, 100);
        const n = g.spark.length, r0 = Math.max(0, n - 4);
        const gt = growthText(g.pct, locale);
        return (
          <li key={g.generation} className={`fr-gen${g.counted ? "" : " is-thin"}`}>
            <b>{genLabel(locale, g.generation)}</b>
            {large && <span className={`fr-gen-pct fr-num is-${gt.dir}`}>{g.counted ? gt.text : c(locale, "not_counted")}</span>}
            <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img"
              aria-label={`${genLabel(locale, g.generation)}: ${c(locale, "interest")} ${g.counted ? gt.text : c(locale, "not_counted")}`}>
              <line x1={pad} x2={W - pad} y1={H - pad} y2={H - pad} className="fr-l-axis" vectorEffect="non-scaling-stroke" />
              {r0 > 0 && <path d={seg(g.spark, 0, r0, x, y)} className="fr-l-base" fill="none" vectorEffect="non-scaling-stroke" />}
              <path d={seg(g.spark, r0, n - 1, x, y)} className="fr-l-recent" fill="none" vectorEffect="non-scaling-stroke" />
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
  if (pct === null) return { text: "", dir: "none" };
  if (Math.abs(pct) < 1) return { text: c(locale, "flat"), dir: "flat" };
  return pct > 0 ? { text: `▲ ${pct}%`, dir: "up" } : { text: `▼ ${Math.abs(pct)}%`, dir: "down" };
}
