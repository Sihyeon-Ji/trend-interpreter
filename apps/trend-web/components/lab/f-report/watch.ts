"use client";

import { useCallback, useSyncExternalStore } from "react";

/* 지켜보기 — 브라우저(localStorage)에만. 익명은 서버에 설정을 갖지 않는다.
   저장할 때의 단계·리스크를 함께 적어 두어, 다음에 왔을 때 무엇이 달라졌는지 견줄 수 있다. */
export interface WatchItem { id: string; name: string; lang: string; at: string; stage?: string | null; risk?: string | null }
const KEY = "fr:watch";
const EVENT = "fr:watch";
const EMPTY: WatchItem[] = [];
let cacheRaw: string | null = null;
let cacheVal: WatchItem[] = EMPTY;

function read(): WatchItem[] {
  if (typeof window === "undefined") return EMPTY;
  let raw: string | null = null;
  try { raw = window.localStorage.getItem(KEY); } catch { return cacheVal; }   // 사생활 보호 모드 등 — 마지막으로 읽은 값으로
  if (raw === cacheRaw) return cacheVal;
  cacheRaw = raw;
  try {
    const v = raw ? (JSON.parse(raw) as WatchItem[]) : EMPTY;
    cacheVal = Array.isArray(v) ? v.filter((x) => x && typeof x.id === "string" && typeof x.name === "string") : EMPTY;
  } catch {
    cacheVal = EMPTY;
  }
  return cacheVal;
}
function write(items: WatchItem[]) {
  try { window.localStorage.setItem(KEY, JSON.stringify(items)); } catch { cacheRaw = null; cacheVal = items; }   // 저장이 막힌 브라우저 — 화면만 바꾼다
  window.dispatchEvent(new Event(EVENT));
}
function subscribe(cb: () => void) {
  window.addEventListener(EVENT, cb);
  window.addEventListener("storage", cb);
  return () => { window.removeEventListener(EVENT, cb); window.removeEventListener("storage", cb); };
}

export function useWatchlist() {
  const items = useSyncExternalStore(subscribe, read, () => EMPTY);
  const has = useCallback((id: string) => items.some((x) => x.id === id), [items]);
  const toggle = useCallback((item: Omit<WatchItem, "at">) => {
    const cur = read();
    write(cur.some((x) => x.id === item.id) ? cur.filter((x) => x.id !== item.id) : [{ ...item, at: new Date().toISOString() }, ...cur].slice(0, 50));
  }, []);
  const remove = useCallback((id: string) => write(read().filter((x) => x.id !== id)), []);
  return { items, has, toggle, remove };
}
