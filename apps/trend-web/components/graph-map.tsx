import { t, type Locale } from "@/lib/i18n";
import { regionLabel } from "@/lib/labels";
import type { GraphCountry } from "@/lib/types";

/* 콘텐츠를 가운데, 나라를 둘레에 둔 연결 그림. 나라 원의 크기는 항목 수. 나라를 누르면 아래 칸(#country-XX)으로 간다 —
   링크라서 스크립트 없이 동작하고, 부드러운 이동은 globals.css 가 움직임 줄이기 설정을 따라 켠다. */
const W = 640, H = 380, CX = W / 2, CY = H / 2, RX = 240, RY = 130;

export function GraphMap({ name, countries, locale }: { name: string; countries: GraphCountry[]; locale: Locale }) {
  const max = Math.max(1, ...countries.map((c) => c.items.length));
  return (
    <figure className="space-y-2">
      <svg viewBox={`0 0 ${W} ${H}`} role="group" aria-label={t(locale, "graph_map").replace("{name}", name)} className="h-auto w-full max-w-[720px]">
        {countries.map((c, i) => {
          const a = (2 * Math.PI * i) / countries.length - Math.PI / 2;
          const x = CX + RX * Math.cos(a), y = CY + RY * Math.sin(a);
          return <line key={c.region} x1={CX} y1={CY} x2={x} y2={y} className="stroke-hairline-strong" strokeWidth={1} />;
        })}
        <circle cx={CX} cy={CY} r={38} className="fill-background stroke-ink" strokeWidth={1.5} />
        <text x={CX} y={CY} textAnchor="middle" dominantBaseline="middle" className="fill-ink text-[13px] font-medium">{name.length > 10 ? `${name.slice(0, 9)}…` : name}</text>
        {countries.map((c, i) => {
          const a = (2 * Math.PI * i) / countries.length - Math.PI / 2;
          const x = CX + RX * Math.cos(a), y = CY + RY * Math.sin(a);
          const r = 14 + 18 * Math.sqrt(c.items.length / max);
          const label = regionLabel(locale, c.region);
          return (
            <a key={c.region} href={`#country-${c.region}`} aria-label={`${label} ${t(locale, "graph_items").replace("{n}", String(c.items.length))}`} className="group">
              <circle cx={x} cy={y} r={r} className="fill-background stroke-ink group-hover:stroke-link-blue group-focus-visible:stroke-link-blue" strokeWidth={1} />
              <text x={x} y={y} textAnchor="middle" dominantBaseline="middle" className="fill-ink text-[12px] tabular-nums">{c.items.length}</text>
              <text x={x} y={y + r + 13} textAnchor="middle" className="fill-charcoal text-[12px] group-hover:fill-ink">{label}</text>
            </a>
          );
        })}
      </svg>
      <figcaption className="text-[13px] text-steel">{t(locale, "graph_map_hint")}</figcaption>
    </figure>
  );
}
