"use client";

/* 이 브라우저에만 두는 두 가지 — 지켜보는 밈과 지난 방문 시각. 익명은 서버 쪽 설정을 갖지 않는다(CLAUDE.md).
   useSyncExternalStore 로 읽는다: 서버 그림은 '없음' 으로 그리고, 하이드레이션 뒤 브라우저 값으로 다시 그린다. */
import { useSyncExternalStore } from "react";

const WATCH_KEY = "lab-o-report:watch";
const SEEN_KEY = "lab-o-report:seen";      // 마지막으로 리포트를 본 때
const BASE_KEY = "lab-o-report:baseline";  // 이 탭에서 '지난 방문' 으로 견줄 때 (새로 고쳐도 그대로)

export interface Watched { id: string; name: string; lang?: string }

const listeners = new Set<() => void>();
const notify = () => listeners.forEach((l) => l());

function subscribe(l: () => void) {
  listeners.add(l);
  const onStorage = (e: StorageEvent) => { if (e.key === WATCH_KEY || e.key === SEEN_KEY) l(); };
  window.addEventListener("storage", onStorage);
  return () => { listeners.delete(l); window.removeEventListener("storage", onStorage); };
}

function read(key: string, store: "local" | "session" = "local"): string | null {
  try { return (store === "local" ? window.localStorage : window.sessionStorage).getItem(key); } catch { return null; }
}
function write(key: string, value: string, store: "local" | "session" = "local") {
  try { (store === "local" ? window.localStorage : window.sessionStorage).setItem(key, value); } catch { /* 사생활 보호 모드 등 — 저장 없이 둔다 */ }
}

/* ── 지켜보는 밈 ── */
let watchRaw: string | null = null;
let watchList: Watched[] = [];
const EMPTY: Watched[] = [];

function watchSnapshot(): Watched[] {
  const raw = read(WATCH_KEY);
  if (raw !== watchRaw) {
    watchRaw = raw;
    try {
      const v = raw ? (JSON.parse(raw) as unknown) : [];
      watchList = Array.isArray(v) ? v.filter((x): x is Watched => !!x && typeof x.id === "string" && typeof x.name === "string").slice(0, 60) : [];
    } catch {
      watchList = [];
    }
  }
  return watchList;
}

export function useWatchlist(): Watched[] {
  return useSyncExternalStore(subscribe, watchSnapshot, () => EMPTY);
}

export function toggleWatch(item: Watched) {
  const now = watchSnapshot();
  const next = now.some((w) => w.id === item.id) ? now.filter((w) => w.id !== item.id) : [{ id: item.id, name: item.name, lang: item.lang }, ...now];
  write(WATCH_KEY, JSON.stringify(next));
  notify();
}

/* ── 지난 방문 ──
   탭에서 처음 읽을 때 한 번만: 저장된 '마지막으로 본 때' 를 이 탭의 기준으로 옮겨 두고, 마지막으로 본 때를 지금으로 바꾼다.
   같은 탭에서 새로 고치거나 항목에 다녀와도 기준은 그대로라 '새로 실림' 표시가 사라지지 않는다. */
export interface LastVisit { at: string | null; old: boolean }   // at = null 이면 처음, old = 일주일보다 오래됨
let baseline: LastVisit | undefined;
const WEEK = 7 * 86_400_000;

function baselineSnapshot(): LastVisit {
  if (baseline !== undefined) return baseline;
  let base = read(BASE_KEY, "session");
  if (base === null) {
    base = read(SEEN_KEY) ?? "none";
    write(BASE_KEY, base, "session");
  }
  write(SEEN_KEY, new Date().toISOString());
  const at = base === "none" ? null : base;
  const t = at ? Date.parse(at) : NaN;
  baseline = { at: Number.isNaN(t) ? null : at, old: !Number.isNaN(t) && Date.now() - t > WEEK };
  return baseline;
}

/** 지난 방문(없으면 at=null = 처음). 서버 그림과 하이드레이션 중에는 undefined — '이번 주' 로 그린다 */
export function useLastVisit(): LastVisit | undefined {
  return useSyncExternalStore(subscribe, baselineSnapshot, () => undefined);
}
