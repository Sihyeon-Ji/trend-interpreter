"use client";

/* 3D 지구 (globe.gl). 화면에서만 로드한다. 상태는 부모(TrendExplorer)가 갖고, 여기는 그리기만 한다. */
import { useEffect, useRef, useState, type MutableRefObject } from "react";
import type { GlobeInstance } from "globe.gl";
import { FEATURES, codeOf, type CountryFeature } from "@/lib/trends/geo";

export interface GlobeBubble { region: string; lat: number; lng: number; title: string; sub: string; strong?: boolean }
export interface GlobeArc { startLat: number; startLng: number; endLat: number; endLng: number }
export interface GlobeRing { lat: number; lng: number }
export interface GlobeFocus { lat: number; lng: number; altitude: number; nonce: number }
export interface GlobeApi { zoom(factor: number): void; reset(): void; setRotate(on: boolean): boolean }

const HOME = { lat: 18, lng: 122 };
const C = { land: "#e6e8eb", data: "#cdd2d8", hover: "#b9c0c8", topic: "#9aa1aa", selected: "#1a1a1a", ocean: "#f4f6f8" };
// 말풍선이 겹치는 동아시아·동남아는 픽셀 단위로 비켜 놓고 지시선을 단다 [dx, dy]
const BUBBLE_OFFSET: Record<string, [number, number]> = {
  KR: [-54, -22], JP: [58, -26], TW: [46, 22], PH: [44, 6], VN: [-36, 30], TH: [-98, -34], CN: [-10, -8], ID: [10, 24], MY: [-60, 30], SG: [-40, 48],
  GB: [-30, -18], DE: [40, -20], AE: [-20, 0], IN: [-20, -6],
};
// 화면 크기에 맞는 처음 배율: 좁으면 멀리서
const homeAltitude = (w: number, h: number) => (w < 640 ? 3.2 : w / h < 1.25 ? 2.8 : 2.45);

interface Props {
  regionsWithData: string[];
  highlighted: string[];
  selected: string | null;
  bubbles: GlobeBubble[];
  arcs: GlobeArc[];
  rings: GlobeRing[];
  focus: GlobeFocus | null;
  onSelect: (region: string) => void;
  apiRef: MutableRefObject<GlobeApi | null>;
  loadingLabel: string;
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
  node.className = "globe-bubble" + (b.strong ? " is-strong" : "") + (dx || dy ? " is-offset" : "");
  node.style.transform = `translate(calc(-50% + ${dx}px), calc(-100% - 10px + ${dy}px))`;
  node.innerHTML = `<span class="globe-bubble__region">${esc(b.sub)}</span><span class="globe-bubble__term">${esc(b.title)}</span>`;
  node.onclick = (e) => { e.stopPropagation(); onSelect(b.region); };
  anchor.appendChild(node);
  return anchor;
}

export function TrendGlobe(props: Props) {
  const box = useRef<HTMLDivElement>(null);
  const globe = useRef<GlobeInstance | null>(null);
  const hover = useRef<string | null>(null);
  const moved = useRef(false); // 사용자가 직접 돌렸으면 크기 바뀔 때 배율을 건드리지 않는다
  const latest = useRef(props);
  const [ready, setReady] = useState(false);
  useEffect(() => { latest.current = props; });

  // 색은 항상 최신 props 를 본다
  const capColor = (f: object) => {
    const code = codeOf(f as CountryFeature);
    const p = latest.current;
    if (!code) return C.land;
    if (code === p.selected) return C.selected;
    if (p.highlighted.includes(code)) return C.topic;
    if (code === hover.current) return C.hover;
    return p.regionsWithData.includes(code) ? C.data : C.land;
  };
  const apply = (g: GlobeInstance, p: Props) => {
    g.polygonCapColor(capColor);
    g.arcsData(p.arcs as object[]);
    g.ringsData(p.rings as object[]);
    const max = (box.current?.clientWidth ?? 1000) < 640 ? 6 : 99; // 좁은 화면은 항목 많은 6개 나라만
    g.htmlElementsData(p.bubbles.slice(0, max) as object[]);
  };

  useEffect(() => {
    let disposed = false;
    let ro: ResizeObserver | undefined;
    let idle: ReturnType<typeof setTimeout> | undefined;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    (async () => {
      const { default: Globe } = await import("globe.gl");
      if (disposed || !box.current) return;
      const el = box.current;
      const g = new Globe(el, { animateIn: false, rendererConfig: { antialias: true, alpha: true } });
      g.backgroundColor("rgba(0,0,0,0)").showAtmosphere(false).showGraticules(false)
        .polygonsData(FEATURES).polygonAltitude(0.004).polygonSideColor(() => "rgba(0,0,0,0)").polygonStrokeColor(() => "#ffffff")
        .polygonCapColor(capColor).polygonsTransitionDuration(200)
        .onPolygonClick((f) => {
          const code = codeOf(f as CountryFeature);
          if (code && latest.current.regionsWithData.includes(code)) latest.current.onSelect(code);
        })
        .onPolygonHover((f) => {
          const code = f ? codeOf(f as CountryFeature) : null;
          hover.current = code && latest.current.regionsWithData.includes(code) ? code : null;
          el.style.cursor = hover.current ? "pointer" : "grab";
          g.polygonCapColor(capColor);
        })
        .arcStartLat("startLat").arcStartLng("startLng").arcEndLat("endLat").arcEndLng("endLng")
        .arcColor(() => "rgba(26,26,26,0.85)").arcStroke(0.55).arcAltitudeAutoScale(0.16)
        .arcDashLength(0.45).arcDashGap(0.25).arcDashAnimateTime(reduced ? 0 : 1600).arcsTransitionDuration(0)
        .ringLat("lat").ringLng("lng").ringAltitude(0.006).ringMaxRadius(5).ringPropagationSpeed(1.6).ringRepeatPeriod(1000)
        .ringColor(() => (t: number) => `rgba(26,26,26,${Math.max(0, 0.55 - t * 0.55).toFixed(2)})`)
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
      controls.autoRotate = !reduced;
      controls.autoRotateSpeed = 0.35;
      controls.enablePan = false;
      controls.minDistance = 140;
      controls.maxDistance = 560;
      const rest = () => { if (idle) clearTimeout(idle); idle = setTimeout(() => { if (!latest.current.selected && !reduced) controls.autoRotate = true; }, 8000); };
      controls.addEventListener("start", () => { moved.current = true; controls.autoRotate = false; if (idle) clearTimeout(idle); });
      controls.addEventListener("end", rest);
      const size = () => {
        const r = el.getBoundingClientRect();
        g.width(r.width).height(r.height);
        if (!moved.current && !latest.current.focus) g.pointOfView({ ...HOME, altitude: homeAltitude(r.width, r.height) }, 0);
      };
      size();
      ro = new ResizeObserver(size);
      ro.observe(el);
      globe.current = g;
      latest.current.apiRef.current = {
        zoom(factor) { moved.current = true; const pov = g.pointOfView(); g.pointOfView({ ...pov, altitude: Math.min(4.5, Math.max(0.4, pov.altitude * factor)) }, 350); },
        reset() { moved.current = false; const r = el.getBoundingClientRect(); g.pointOfView({ ...HOME, altitude: homeAltitude(r.width, r.height) }, 800); controls.autoRotate = !reduced; },
        setRotate(on) { controls.autoRotate = on; return on; },
      };
      setReady(true);
      apply(g, latest.current);
      if (latest.current.focus) g.pointOfView(latest.current.focus, 0);
    })();
    return () => {
      disposed = true;
      ro?.disconnect();
      if (idle) clearTimeout(idle);
      globe.current?._destructor();
      globe.current = null;
      latest.current.apiRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (globe.current) apply(globe.current, props);
  }, [props.bubbles, props.arcs, props.rings, props.selected, props.highlighted, props.regionsWithData]); // eslint-disable-line react-hooks/exhaustive-deps

  // 카메라 이동은 nonce 가 바뀔 때만
  useEffect(() => {
    const g = globe.current;
    if (!g || !props.focus) return;
    g.controls().autoRotate = false;
    g.pointOfView({ lat: props.focus.lat, lng: props.focus.lng, altitude: props.focus.altitude }, 900);
  }, [props.focus]);

  return (
    <div className="relative h-full w-full">
      <div ref={box} className="h-full w-full cursor-grab" aria-label="globe" role="img" />
      {!ready && <p className="absolute inset-0 flex items-center justify-center text-[13px] text-steel">{props.loadingLabel}</p>}
    </div>
  );
}
