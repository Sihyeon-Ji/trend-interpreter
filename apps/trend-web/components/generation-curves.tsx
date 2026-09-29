import { t, type Locale } from "@/lib/i18n";
import { L } from "@/lib/labels";
import type { GenerationCurve } from "@/lib/trends/types";

/* 나이대별 검색 관심 — 나이대마다 작은 선 하나(한 그림에 선 다섯 개를 겹치면 옅은 회색 둘이 구분되지 않았다).
   선은 먹색 하나, 이름과 정점(연.월)은 HTML 글자로 둔다(SVG 글자는 휴대폰에서 6px 까지 줄었다). */
const ORDER = ["10s", "20s", "30s", "40s", "50s+"];
const peakLabel = (d: string) => d.slice(0, 7).replace("-", ".");

export function GenerationCurves({ curves, locale }: { curves: GenerationCurve[]; locale: Locale }) {
  const labels = L(locale);
  const series = curves.filter((c) => c.points.length > 1).sort((a, b) => ORDER.indexOf(a.generation) - ORDER.indexOf(b.generation));
  if (!series.length) return null;
  const W = 120, H = 40, pad = 3;
  // 모든 칸이 같은 가로축(날짜)을 쓴다 — 누가 먼저 튀었는지 칸끼리 견줄 수 있게
  const dates = Array.from(new Set(series.flatMap((c) => c.points.map((p) => p[0])))).sort();
  const x = (d: string) => pad + (dates.indexOf(d) / Math.max(1, dates.length - 1)) * (W - pad * 2);
  const y = (v: number) => pad + (1 - v / 100) * (H - pad * 2);
  const gen = (g: string) => labels.generation[g as keyof typeof labels.generation] ?? g;
  return (
    <figure className="space-y-2">
      <ul className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3 lg:grid-cols-5">
        {series.map((c) => {
          const d = c.points.map(([dt, v], i) => `${i ? "L" : "M"}${x(dt).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
          return (
            <li key={c.generation} className="min-w-0">
              <p className="text-[13px] font-medium text-ink">{gen(c.generation)}</p>
              <svg viewBox={`0 0 ${W} ${H}`} className="mt-1 block h-10 w-full max-w-[160px] text-ink" aria-hidden>
                <line x1={pad} x2={W - pad} y1={H - pad} y2={H - pad} className="stroke-hairline" strokeWidth="1" />
                <path d={d} fill="none" stroke="currentColor" strokeWidth="1.25" strokeLinejoin="round" />
              </svg>
              {c.peak_date && <p className="mt-1 text-[12px] tabular-nums text-steel">{t(locale, "term_gen_peak")} {peakLabel(c.peak_date)}</p>}
            </li>
          );
        })}
      </ul>
      <figcaption className="text-[12px] leading-[1.5] text-steel">
        {dates.length > 1 && <span className="tabular-nums">{peakLabel(dates[0])}–{peakLabel(dates[dates.length - 1])}. </span>}
        {t(locale, "term_gen_curves_hint")}
      </figcaption>
    </figure>
  );
}
