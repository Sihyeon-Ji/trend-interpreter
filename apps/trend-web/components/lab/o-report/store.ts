"use client";

/* 이 브라우저에만 두는 두 가지 — 지켜보는 밈과 지난 방문 시각. 익명은 서버 쪽 설정을 갖지 않는다(CLAUDE.md).
   useSyncExternalStore 로 읽는다: 서버 그림은 '없음' 으로 그리고, 하이드레이션 뒤 브라우저 값으로 다시 그린다.
   지켜보는 밈은 누른 때의 단계·쓸 때 조심을 함께 적어 둔다 — 다음에 와서 '무엇이 바뀌었나' 를 말하려고(09-29 검토). */
import { useEffect, useState, useSyncExternalStore } from "react";
import type { Lifecycle } from "@/lib/contract/types";
import type { Locale } from "@/lib/i18n";
import type { Change, RiskKey, Row } from "@/lib/lab/o-report";
import type { WatchState } from "@/lib/lab/o-report-data";

const WATCH_KEY = "lab-o-report:watch";
const SEEN_KEY = "lab-o-report:seen";      // 마지막으로 리포트를 본 때
const BASE_KEY = "lab-o-report:baseline";  // 이 탭에서 '지난 방문' 으로 견줄 때 (새로 고쳐도 그대로)

export interface Watched {
  id: string;
  name: string;
  lang?: string;
  at?: string;               // 지켜보기 시작한 때
  lifecycle?: Lifecycle;     // 그때의 단계 — 예전에 저장한 것에는 없다(그러면 단계 변화는 말하지 않는다)
  risk?: RiskKey;            // 그때의 쓸 때 조심
}

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

/** 넣거나 뺀다. 넣을 때 지금의 단계·쓸 때 조심을 함께 적는다 */
export function toggleWatch(item: Omit<Watched, "at">) {
  const now = watchSnapshot();
  const next = now.some((w) => w.id === item.id)
    ? now.filter((w) => w.id !== item.id)
    : [{ id: item.id, name: item.name, lang: item.lang, lifecycle: item.lifecycle, risk: item.risk, at: new Date().toISOString() }, ...now].slice(0, 60);
  write(WATCH_KEY, JSON.stringify(next));
  notify();
}

/* ── 지켜보는 밈의 지금 상태 ──
   지금 목록에 있는 밈은 그 줄이 곧 지금 상태다. 목록 밖(다른 지역·빠진 밈)만 같은 사이트의 읽기 전용 경로에 묻는다.
   같은 묶음을 두 곳(지난 방문 줄, 지켜보는 밈 탭)이 물으면 한 번만 부른다. */
const stateCache = new Map<string, Promise<WatchState[] | null>>();

function fetchStates(ids: string[], locale: Locale): Promise<WatchState[] | null> {
  const key = `${locale}|${[...ids].sort().join(",")}`;
  let p = stateCache.get(key);
  if (!p) {
    p = fetch(`/lab/o-report/api/watch?locale=${locale}&ids=${ids.map(encodeURIComponent).join(",")}`)
      .then((r) => (r.ok ? (r.json() as Promise<WatchState[]>) : null))
      .catch(() => null);
    stateCache.set(key, p);
  }
  return p;
}

export type WatchNow = { status: "idle" | "loading" | "ready" | "failed"; outside: Map<string, WatchState> };

export function useOutsideStates(watch: Watched[], inLists: (id: string) => boolean, locale: Locale): WatchNow {
  const ids = watch.map((w) => w.id).filter((id) => !inLists(id));
  const key = ids.join(",");
  const [got, setGot] = useState<{ key: string; states: WatchState[] | null } | null>(null);
  useEffect(() => {
    if (!key) return;
    let live = true;
    fetchStates(key.split(","), locale).then((states) => { if (live) setGot({ key, states }); });
    return () => { live = false; };
  }, [key, locale]);
  if (!key) return { status: "idle", outside: new Map() };
  if (!got || got.key !== key) return { status: "loading", outside: new Map() };
  if (!got.states) return { status: "failed", outside: new Map() };
  return { status: "ready", outside: new Map(got.states.map((s) => [s.id, s])) };
}

/** 지켜보기 시작한 뒤 달라진 것. now 가 없으면(아직 모름) 빈 목록 */
export interface WatchDiff { stage?: [Lifecycle, Lifecycle]; risk?: [RiskKey, RiskKey]; meaning?: boolean; gone?: boolean }

export function diffOf(w: Watched, now: { lifecycle: Lifecycle; risk: RiskKey } | "gone" | null, changes: Change[]): WatchDiff {
  if (now === "gone") return { gone: true };
  const d: WatchDiff = {};
  if (now && w.lifecycle && w.lifecycle !== now.lifecycle) d.stage = [w.lifecycle, now.lifecycle];
  if (now && w.risk && w.risk !== now.risk) d.risk = [w.risk, now.risk];
  if (w.at && changes.some((c) => c.kind === "meaning_changed" && c.id === w.id && Date.parse(c.at) > Date.parse(w.at!))) d.meaning = true;
  return d;
}

export const changed = (d: WatchDiff) => !!(d.stage || d.risk || d.meaning || d.gone);

/** 지금 목록의 줄(단계·쓸 때 조심만 있으면 된다) */
export type Current = Pick<Row, "lifecycle" | "risk">;

/** 한 줄(지금 목록의 줄)이나 목록 밖 상태에서 '지금' 을 꺼낸다 */
export function nowOf(id: string, rows: Map<string, Current>, outside: Map<string, WatchState>): { lifecycle: Lifecycle; risk: RiskKey } | "gone" | null {
  const r = rows.get(id);
  if (r) return { lifecycle: r.lifecycle, risk: r.risk ?? "none" };
  const s = outside.get(id);
  if (!s) return null;
  if (s.gone) return "gone";
  return s.lifecycle ? { lifecycle: s.lifecycle, risk: s.risk ?? "none" } : null;
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
