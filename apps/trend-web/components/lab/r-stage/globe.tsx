"use client";

import { geoGraticule10, geoOrthographic, geoPath } from "d3-geo";
import { animate, useReducedMotion } from "motion/react";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import { FEATURES } from "@/lib/trends/geo";
import type { Market } from "./copy";

/* 시장의 표지 — 국기 대신 그 시장 쪽으로 돌린 작은 지구. 나라 깃발은 '영어권' 을 그릴 수 없고 정치적 뜻이 붙는다.
   시장이 바뀌면 지구가 그쪽으로 돈다(무엇이 바뀌었는지 보여 주는 움직임). 움직임 줄이기 설정이면 바로 그 자리로. */

const CENTER: Record<Market, [number, number]> = { KR: [127.8, 36.4], JP: [137.5, 36.5], GLOBAL: [-42, 40] };
// 한국·일본은 작아서 그 둘레를 당겨 본다(렌즈). 영어권은 대서양 양쪽이 다 보이게 반구 그대로
const ZOOM: Record<Market, number> = { KR: 2.6, JP: 2.2, GLOBAL: 1 };
// 위치 표시 점 — 나라가 몇 픽셀뿐이어도 어디인지 보이게
const PINS: Record<Market, [number, number][]> = { KR: [[127.8, 36.4]], JP: [[138.5, 36.2]], GLOBAL: [] };
// world-atlas 숫자 id — 한국 410, 일본 392, 영어권은 미국·영국·캐나다·아일랜드·호주·뉴질랜드
const LIT: Record<Market, string[]> = { KR: ["410"], JP: ["392"], GLOBAL: ["840", "826", "124", "372", "036", "554"] };

const norm = (d: number) => ((((d + 180) % 360) + 360) % 360) - 180;
const GRATICULE = geoGraticule10();

export function MiniGlobe({ market, size = 32, tone = "ink", className = "" }: { market: Market; size?: number; tone?: "ink" | "blue" | "mute"; className?: string }) {
  const reduce = useReducedMotion();
  // [경도, 위도, 확대]
  const [view, setView] = useState<[number, number, number]>([...CENTER[market], ZOOM[market]]);
  const from = useRef<[number, number, number]>([...CENTER[market], ZOOM[market]]);

  useEffect(() => {
    const to: [number, number, number] = [...CENTER[market], ZOOM[market]];
    const start = from.current;
    if (start[0] === to[0] && start[1] === to[1] && start[2] === to[2]) return;
    if (reduce) {
      from.current = to;
      const id = requestAnimationFrame(() => setView(to));
      return () => cancelAnimationFrame(id);
    }
    const dLon = norm(to[0] - start[0]);
    const dLat = to[1] - start[1];
    const dZoom = to[2] - start[2];
    const ctl = animate(0, 1, {
      type: "spring", stiffness: 200, damping: 22.6,   // 느린 공간 스프링(감쇠 0.8) — 지구는 무거운 물체
      onUpdate: (p) => {
        const now: [number, number, number] = [start[0] + dLon * p, start[1] + dLat * p, start[2] + dZoom * p];
        from.current = now;
        setView(now);
      },
    });
    return () => ctl.stop();
  }, [market, reduce]);

  const lit = LIT[market];
  const paths = useMemo(() => {
    const r = size / 2 - 1;
    const proj = geoOrthographic().scale(r * view[2]).translate([size / 2, size / 2]).rotate([-view[0], -view[1]]).clipAngle(90).precision(0.6);
    const path = geoPath(proj);
    const land: string[] = [];
    const on: string[] = [];
    for (const f of FEATURES) {
      const d = path(f as never);
      if (!d) continue;
      (lit.includes(String(f.id)) ? on : land).push(d);
    }
    // 서버와 브라우저의 삼각함수 끝자리가 달라 하이드레이션이 어긋나지 않게 반올림
    const pins = PINS[market].map((ll) => proj(ll)).filter((p): p is [number, number] => !!p).map(([x, y]) => [Math.round(x * 10) / 10, Math.round(y * 10) / 10]);
    return { land: land.join(""), on: on.join(""), grid: path(GRATICULE) ?? "", r, pins };
  }, [view, size, lit, market]);
  const clip = `rs-globe-${useId().replace(/:/g, "")}`;

  return (
    <svg className={`rs-globe ${className}`} data-tone={tone} width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true" focusable="false">
      <defs><clipPath id={clip}><circle cx={size / 2} cy={size / 2} r={paths.r} /></clipPath></defs>
      <circle className="rs-globe-sea" cx={size / 2} cy={size / 2} r={paths.r} />
      <g clipPath={`url(#${clip})`}>
        {size >= 64 ? <path className="rs-globe-grid" d={paths.grid} /> : null}
        <path className="rs-globe-land" d={paths.land} />
        <path className="rs-globe-lit" d={paths.on} />
        {paths.pins.map(([x, y], i) => <circle key={i} className="rs-globe-pin" cx={x} cy={y} r={Math.max(2.5, size / 14)} />)}
      </g>
      <circle className="rs-globe-rim" cx={size / 2} cy={size / 2} r={paths.r} />
    </svg>
  );
}
