"use client";

/* 3D 지구 (globe.gl). 화면에서만 로드한다. 상태는 부모(TrendExplorer)가 갖고, 여기는 그리기만 한다.
   화면 읽기 프로그램에는 숨긴다(aria-hidden) — 같은 일은 옆의 표가 한다. 자동 회전은 없다(개편 검토: 동작 줄이기·조작 단추가 묻힘). */
import { useEffect, useRef, useState, type MutableRefObject } from "react";
import type { GlobeInstance } from "globe.gl";
import { POINT_ONLY } from "@/components/globe/points";
import { FEATURES, codeOf, type CountryFeature } from "@/lib/trends/geo";

export interface GlobeBubble { region: string; lat: number; lng: number; title: string; sub: string; picked?: boolean; muted?: boolean; titleLang?: string }
export interface GlobeArc { startLat: number; startLng: number; endLat: number; endLng: number }
export interface GlobeRing { lat: number; lng: number }
export interface GlobeFocus { lat: number; lng: number; altitude: number; nonce: number }
export interface GlobeApi { zoom(factor: number): void; reset(): void }

const HOME = { lat: 18, lng: 122 };
// 토큰(docs/트렌드/디자인-개편.md): 바다 옅은 바탕, 땅 선, 칠한 나라 진한 선, 고른 나라 파랑(선택 표시). 검정으로 칠하지 않는다.
const C = { land: "#e4e7eb", shaded: "#cbd0d6", hover: "#b9c0c8", picked: "#1d5bd6", ocean: "#f6f7f9", ink: "#17191c" };
// 말풍선이 겹치는 동아시아·동남아는 픽셀 단위로 비켜 놓고 지시선을 단다 [dx, dy]
const BUBBLE_OFFSET: Record<string, [number, number]> = {
  KR: [-6, -34], JP: [62, -22], TW: [62, 6], HK: [-74, -30], PH: [58, 40], VN: [-70, 18], TH: [-104, -36], ID: [40, 40], MY: [-96, 24], SG: [-44, 82],
  CN: [-10, -8], GB: [-30, -18], DE: [40, -20], AE: [-20, 0], IN: [-20, -6],
};
// 화면 크기에 맞는 처음 배율: 좁으면 멀리서
const homeAltitude = (w: number, h: number) => (w < 640 ? 1.9 : w / h < 1.25 ? 1.05 : 0.95);
const READY_TIMEOUT = 8000;

interface Props {
  shaded: string[];        // 칠하는 나라(지역 탭: 목표 지역, 밈 탭: 그 밈이 보인 나라)
  picked: string[];        // 고른 나라 — 파랑
  selectable: string[];    // 누를 수 있는 나라
  bubbles: GlobeBubble[];
  arcs: GlobeArc[];
  rings: GlobeRing[];
  focus: GlobeFocus | null;
  onSelect: (region: string) => void;
  apiRef: MutableRefObject<GlobeApi | null>;
  loadingLabel: string;
  failedLabel: string;
}

const esc = (s: string) => s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c] as string);

function makeBubble(b: GlobeBubble, onSelect: (r: string) => void) {
  // 렌더러가 바깥 요소의 transform 을 매 프레임 덮어쓰므로, 기준점(0×0) 안에 말풍선을 따로 두고 그 안에서만 비켜 놓는다
  const [dx, dy] = BUBBLE_OFFSET[b.region] ?? [0, 0];
  const anchor = document.createElement("div");
  anchor.className = "globe-anchor";
  if (dx || dy) {
    const tx = dx, ty = dy - 10; // 말풍선 아래 가운데
    const leader = document.createElement("i");
    leader.className = "globe-bubble__leader";
    leader.style.width = `${Math.hypot(tx, ty).toFixed(1)}px`;
    leader.style.transform = `rotate(${Math.atan2(ty, tx).toFixed(4)}rad)`;
    anchor.appendChild(leader);
  }
  const node = document.createElement("button");
  node.type = "button";
  node.tabIndex = -1;   // 같은 일은 표가 한다 — 보이지 않는 뒤편 말풍선에 초점이 머물지 않게
  node.className = "globe-bubble" + (dx || dy ? " is-offset" : "");
  node.style.transform = `translate(calc(-50% + ${dx}px), calc(-100% - 10px + ${dy}px))`;
  if (b.picked) { node.style.borderColor = C.picked; node.style.boxShadow = `inset 0 0 0 1px ${C.picked}`; }
  const lang = b.titleLang ? ` lang="${esc(b.titleLang)}"` : "";
  node.innerHTML = `<span class="globe-bubble__region" style="font-size:12px;color:var(--charcoal)">${esc(b.sub)}</span>`
    + `<span class="globe-bubble__term"${lang} style="font-size:13px;font-variant-numeric:tabular-nums;${b.muted ? "font-weight:400;color:var(--steel)" : ""}">${esc(b.title)}</span>`;
  node.onclick = (e) => { e.stopPropagation(); onSelect(b.region); };
  anchor.appendChild(node);
  return anchor;
}

function webgl(): boolean {
  try {
    const c = document.createElement("canvas");
    return !!(c.getContext("webgl2") || c.getContext("webgl"));
  } catch {
    return false;
  }
}

export function TrendGlobe(props: Props) {
  const box = useRef<HTMLDivElement>(null);
  const globe = useRef<GlobeInstance | null>(null);
  const hover = useRef<string | null>(null);
  const moved = useRef(false); // 사용자가 직접 돌렸으면 크기 바뀔 때 배율을 건드리지 않는다
  const reduced = useRef(false);
  const latest = useRef(props);
  const [state, setState] = useState<"loading" | "ready" | "failed">("loading");
  useEffect(() => { latest.current = props; });

  // 색은 항상 최신 props 를 본다
  const capColor = (f: object) => {
    const code = codeOf(f as CountryFeature);
    const p = latest.current;
    if (!code) return C.land;
    if (p.picked.includes(code)) return C.picked;
    if (code === hover.current) return C.hover;
    return p.shaded.includes(code) ? C.shaded : C.land;
  };
  // 도형이 없는 목표 지역(홍콩·싱가포르)은 점으로
  const points = (p: Props) => Object.entries(POINT_ONLY).filter(([code]) => p.shaded.includes(code) || p.picked.includes(code)).map(([code, c]) => ({ code, ...c }));
  const apply = (g: GlobeInstance, p: Props) => {
    g.polygonCapColor(capColor);
    g.arcsData(p.arcs as object[]);
    g.ringsData((reduced.current ? [] : p.rings) as object[]);
    g.pointsData(points(p));
    g.htmlElementsData(p.bubbles as object[]);
  };

  useEffect(() => {
    let disposed = false;
    let ro: ResizeObserver | undefined;
    reduced.current = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const reducedMotion = reduced.current;
    const timeout = setTimeout(() => { if (!globe.current && !disposed) setState("failed"); }, READY_TIMEOUT);
    (async () => {
      if (!webgl()) throw new Error("no webgl");
      const { default: Globe } = await import("globe.gl");
      if (disposed || !box.current) return;
      const el = box.current;
      const g = new Globe(el, { animateIn: false, rendererConfig: { antialias: true, alpha: true } });
      const selectable = (code: string | undefined | null) => !!code && latest.current.selectable.includes(code);
      g.backgroundColor("rgba(0,0,0,0)").showAtmosphere(false).showGraticules(false)
        .polygonsData(FEATURES).polygonAltitude(0.004).polygonSideColor(() => "rgba(0,0,0,0)").polygonStrokeColor(() => "#ffffff")
        .polygonCapColor(capColor).polygonsTransitionDuration(reducedMotion ? 0 : 200)
        .onPolygonClick((f) => {
          const code = codeOf(f as CountryFeature);
          if (selectable(code)) latest.current.onSelect(code!);
        })
        .onPolygonHover((f) => {
          const code = f ? codeOf(f as CountryFeature) : null;
          hover.current = selectable(code) ? code : null;
          el.style.cursor = hover.current ? "pointer" : "grab";
          g.polygonCapColor(capColor);
        })
        .pointLat("lat").pointLng("lng").pointAltitude(0.008).pointRadius(0.45).pointsMerge(false).pointsTransitionDuration(0)
        .pointColor((d) => (latest.current.picked.includes((d as { code: string }).code) ? C.picked : C.ink))
        .onPointClick((d) => { const code = (d as { code: string }).code; if (selectable(code)) latest.current.onSelect(code); })
        .arcStartLat("startLat").arcStartLng("startLng").arcEndLat("endLat").arcEndLng("endLng")
        .arcColor(() => "rgba(23,25,28,0.85)").arcStroke(0.55).arcAltitudeAutoScale(0.16)
        .arcDashLength(reducedMotion ? 1 : 0.45).arcDashGap(reducedMotion ? 0 : 0.25).arcDashAnimateTime(reducedMotion ? 0 : 1600).arcsTransitionDuration(0)
        .ringLat("lat").ringLng("lng").ringAltitude(0.006).ringMaxRadius(5).ringPropagationSpeed(1.6).ringRepeatPeriod(1000)
        .ringColor(() => (t: number) => `rgba(23,25,28,${Math.max(0, 0.55 - t * 0.55).toFixed(2)})`)
        .htmlLat("lat").htmlLng("lng").htmlAltitude(0.012).htmlTransitionDuration(0)
        .htmlElement((d) => makeBubble(d as GlobeBubble, (r) => latest.current.onSelect(r)))
        .htmlElementVisibilityModifier((node, visible) => {
          node.style.opacity = visible ? "1" : "0";
          node.style.pointerEvents = visible ? "auto" : "none";
        });
      const mat = g.globeMaterial() as unknown as { color: { set(c: string): void }; shininess?: number };
      mat.color.set(C.ocean);
      if ("shininess" in mat) mat.shininess = 0;
      const controls = g.controls();
      controls.autoRotate = false;
      controls.enablePan = false;
      controls.minDistance = 140;
      controls.maxDistance = 560;
      controls.addEventListener("start", () => { moved.current = true; });
      // 캔버스 크기는 패널이 잰 값만 쓴다 — 캔버스가 처음 잰 창 폭을 고집해 페이지가 옆으로 넘치던 문제(개편 검토)
      const size = () => {
        const r = el.getBoundingClientRect();
        if (!r.width || !r.height) return;
        g.width(r.width).height(r.height);
        if (!moved.current && !latest.current.focus) g.pointOfView({ ...HOME, altitude: homeAltitude(r.width, r.height) }, 0);
      };
      size();
      ro = new ResizeObserver(size);
      ro.observe(el);
      globe.current = g;
      latest.current.apiRef.current = {
        zoom(factor) { moved.current = true; const pov = g.pointOfView(); g.pointOfView({ ...pov, altitude: Math.min(4.5, Math.max(0.4, pov.altitude * factor)) }, reducedMotion ? 0 : 350); },
        reset() { moved.current = false; const r = el.getBoundingClientRect(); g.pointOfView({ ...HOME, altitude: homeAltitude(r.width, r.height) }, reducedMotion ? 0 : 800); },
      };
      setState("ready");
      apply(g, latest.current);
      if (latest.current.focus) g.pointOfView(latest.current.focus, 0);
    })().catch(() => { if (!disposed) setState("failed"); });
    return () => {
      disposed = true;
      clearTimeout(timeout);
      ro?.disconnect();
      globe.current?._destructor();
      globe.current = null;
      latest.current.apiRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (globe.current) apply(globe.current, props);
  }, [props.bubbles, props.arcs, props.rings, props.picked, props.shaded, props.selectable]); // eslint-disable-line react-hooks/exhaustive-deps

  // 카메라 이동은 nonce 가 바뀔 때만. 동작 줄이기면 바로 옮긴다
  useEffect(() => {
    const g = globe.current;
    if (!g || !props.focus) return;
    g.pointOfView({ lat: props.focus.lat, lng: props.focus.lng, altitude: props.focus.altitude }, reduced.current ? 0 : 900);
  }, [props.focus]);

  return (
    <div className="absolute inset-0">
      <div ref={box} aria-hidden="true" className="absolute inset-0 cursor-grab" />
      {state !== "ready" && (
        <p className="absolute inset-0 flex items-center justify-center px-6 text-center text-[13px] text-steel" role={state === "failed" ? "status" : undefined}>
          {state === "failed" ? props.failedLabel : props.loadingLabel}
        </p>
      )}
    </div>
  );
}
