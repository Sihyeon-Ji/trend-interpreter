/* 이 브라우저에만 남는 작은 기록(최근 초안, 최근 연 밈). localStorage 를 useSyncExternalStore 로 읽는다 —
   effect 안에서 setState 로 옮겨 담지 않게(React 컴파일러 규칙). 서버 렌더에서는 늘 빈 값. */
import { useSyncExternalStore } from "react";

const EVENT = "rf-store";

function createStore<T>(key: string, empty: T, parse: (raw: string) => T) {
  let cache: { raw: string | null; value: T } = { raw: null, value: empty };
  const read = (): T => {
    let raw: string | null = null;
    try {
      raw = window.localStorage.getItem(key);
    } catch {
      raw = null;
    }
    if (raw === cache.raw) return cache.value;
    let value = empty;
    if (raw) {
      try {
        value = parse(raw);
      } catch {
        value = empty;
      }
    }
    cache = { raw, value };
    return value;
  };
  const subscribe = (cb: () => void) => {
    const on = (e: Event) => {
      if (e instanceof StorageEvent && e.key !== key) return;
      cb();
    };
    window.addEventListener("storage", on);
    window.addEventListener(EVENT, on);
    return () => {
      window.removeEventListener("storage", on);
      window.removeEventListener(EVENT, on);
    };
  };
  const write = (value: T | null) => {
    try {
      if (value === null) window.localStorage.removeItem(key);
      else window.localStorage.setItem(key, JSON.stringify(value));
    } catch {
      /* 저장 공간이 꽉 찼거나 막혀 있으면 기록만 남기지 않는다 */
    }
    window.dispatchEvent(new Event(EVENT));
  };
  return { read, subscribe, write, empty };
}

export function useStore<T>(store: ReturnType<typeof createStore<T>>): T {
  return useSyncExternalStore(store.subscribe, store.read, () => store.empty);
}

export interface RecentMeme { id: string; name: string; lang: string }
const NO_MEMES: RecentMeme[] = [];
export const recentMemes = createStore<RecentMeme[]>("rf-recent-memes-v1", NO_MEMES, (raw) => {
  const v = JSON.parse(raw) as unknown;
  return Array.isArray(v) ? (v.filter((x) => x && typeof x.id === "string" && typeof x.name === "string").slice(0, 6) as RecentMeme[]) : NO_MEMES;
});
export function rememberMeme(m: RecentMeme) {
  const cur = recentMemes.read();
  recentMemes.write([m, ...cur.filter((x) => x.id !== m.id)].slice(0, 6));
}

export { createStore };
