/* 브라우저에만 남는 것 두 가지 — 내 목록(별표)과 지난 방문 시각. 익명은 서버에 설정을 갖지 않으므로 localStorage.
   내 목록 항목은 담을 때의 단계·조심 수준을 같이 적어 두어, 다시 왔을 때 무엇이 달라졌는지 말할 수 있다.
   읽기는 useSyncExternalStore 로(서버 렌더와 첫 그리기가 어긋나지 않게). 클라이언트 컴포넌트에서만 부른다. */
import { useSyncExternalStore } from "react";

const WATCH_KEY = "lab-f-editorial:watch";
const VISIT_CUR = "lab-f-editorial:visit";
const VISIT_PREV = "lab-f-editorial:visit-prev";
const SESSION_MS = 30 * 60_000;   // 30분 안에 다시 열면 같은 방문으로 친다

export interface WatchItem {
  id: string;
  name: string;
  lang?: string;
  at?: string;      // 담은 때
  stage?: string;   // 담을 때의 생애주기 키
  risk?: string;    // 담을 때의 조심 종류(caution·avoid·unknown·none). 검사 전이면 없다
}
const EMPTY: WatchItem[] = [];
const listeners = new Set<() => void>();
let cache: { raw: string | null; items: WatchItem[] } = { raw: null, items: EMPTY };

function parse(raw: string | null): WatchItem[] {
  if (!raw) return EMPTY;
  try {
    const v: unknown = JSON.parse(raw);
    return Array.isArray(v)
      ? (v as WatchItem[]).filter((x) => x && typeof x.id === "string" && typeof x.name === "string").slice(0, 100)
      : EMPTY;
  } catch {
    return EMPTY;
  }
}
function read(): WatchItem[] {
  let raw: string | null = null;
  try { raw = localStorage.getItem(WATCH_KEY); } catch { raw = null; }
  if (raw !== cache.raw) cache = { raw, items: parse(raw) };
  return cache.items;
}
function subscribe(cb: () => void) {
  listeners.add(cb);
  window.addEventListener("storage", cb);
  return () => { listeners.delete(cb); window.removeEventListener("storage", cb); };
}
export const useWatchlist = () => useSyncExternalStore(subscribe, read, () => EMPTY);

export function toggleWatch(item: WatchItem) {
  const items = read();
  const next = items.some((x) => x.id === item.id) ? items.filter((x) => x.id !== item.id) : [{ ...item, at: new Date().toISOString() }, ...items];
  try { localStorage.setItem(WATCH_KEY, JSON.stringify(next)); } catch { /* 저장 공간이 없으면 목록은 이번 화면에서만 유지된다 */ }
  listeners.forEach((l) => l());
}

/* 지난 방문 — 이번 방문을 적기 전의 값을 한 번만 읽어 둔다(그래야 '지난 방문 이후' 가 이번 방문으로 덮이지 않는다). */
let prevVisit: string | null | undefined;
function readPrevVisit(): string | null {
  if (prevVisit === undefined) {
    try {
      const now = Date.now();
      const cur = localStorage.getItem(VISIT_CUR);
      if (!cur || now - Date.parse(cur) > SESSION_MS) {
        if (cur) localStorage.setItem(VISIT_PREV, cur);
        localStorage.setItem(VISIT_CUR, new Date(now).toISOString());
      }
      prevVisit = localStorage.getItem(VISIT_PREV);
    } catch {
      prevVisit = null;
    }
  }
  return prevVisit;
}
const never = () => () => {};
/** undefined = 서버(아직 모름), null = 첫 방문, 그 밖은 지난 방문 시각(ISO) */
export const useLastVisit = () => useSyncExternalStore(never, readPrevVisit, () => undefined);
