/* 이 브라우저에만 두는 두 가지 — 스크랩한 밈과 지난번 방문 시각. 익명은 서버에 설정을 갖지 않는다(CLAUDE.md). */

const SCRAPS_KEY = "oe:scraps";
const VISIT_KEY = "oe:visit";
const EVENT = "oe:scraps";
const SESSION_MS = 30 * 60_000;    // 30분 안에 다시 열면 같은 방문으로 본다 — 새로 고침마다 '지난번' 이 지워지지 않게

export interface Scrap {
  id: string;
  name: string;
  lang?: string;
  at: string;               // 스크랩한 때
  lifecycle?: string | null; // 스크랩한 때의 단계·쓸 때 조심 — 다음 방문에 달라졌는지 견준다
  diffusion?: string | null;
  risk?: string | null;
}

/** 사이트 데이터가 막힌 브라우저(개인 창·차단 설정)에서는 window.localStorage 를 읽기만 해도 던진다 — 그때는 저장 없이 동작한다 */
const hasStorage = () => {
  if (typeof window === "undefined") return false;
  try { return !!window.localStorage; } catch { return false; }
};

let cacheRaw: string | null | undefined;
let cacheList: Scrap[] = [];
let memoryOnly = false;          // 저장이 한 번이라도 실패하면 이 탭의 기억만 쓴다

export function readScraps(): Scrap[] {
  if (memoryOnly || !hasStorage()) return cacheList;
  let raw: string | null = null;
  try { raw = window.localStorage.getItem(SCRAPS_KEY); } catch { raw = null; }
  if (raw === cacheRaw) return cacheList;
  cacheRaw = raw;
  try {
    const parsed = raw ? (JSON.parse(raw) as unknown) : [];
    cacheList = Array.isArray(parsed) ? parsed.filter((x): x is Scrap => !!x && typeof x === "object" && typeof (x as Scrap).id === "string" && typeof (x as Scrap).name === "string").slice(0, 60) : [];
  } catch {
    cacheList = [];
  }
  return cacheList;
}

function writeScraps(list: Scrap[]) {
  try {
    window.localStorage.setItem(SCRAPS_KEY, JSON.stringify(list.slice(0, 60)));
  } catch {
    // 저장 공간이 막혀 있으면 이 탭에서만 기억한다(다음 방문에는 없다)
    memoryOnly = true;
    cacheList = list.slice(0, 60);
  }
  window.dispatchEvent(new Event(EVENT));
}

export const isScrapped = (id: string) => readScraps().some((s) => s.id === id);

/** 스크랩을 넣거나 뺀다. 돌려주는 값은 바뀐 뒤의 상태(true = 스크랩됨). */
export function toggleScrap(s: Omit<Scrap, "at">): boolean {
  const list = readScraps();
  if (list.some((x) => x.id === s.id)) {
    writeScraps(list.filter((x) => x.id !== s.id));
    return false;
  }
  writeScraps([{ ...s, at: new Date().toISOString() }, ...list]);
  return true;
}

export function subscribeScraps(cb: () => void) {
  const onStorage = (e: StorageEvent) => { if (e.key === SCRAPS_KEY) cb(); };
  window.addEventListener(EVENT, cb);
  window.addEventListener("storage", onStorage);
  return () => {
    window.removeEventListener(EVENT, cb);
    window.removeEventListener("storage", onStorage);
  };
}

/* 지난번 방문 — 이 탭에서 처음 한 번만 계산해 둔다(같은 탭에서 기사를 오가도 '지난번' 이 그대로). */
let since: { value: string | null } | null = null;

/** 지난번 방문 시각(없으면 null = 처음). 부를 때 이번 방문을 적어 둔다. */
export function lastVisit(): string | null {
  if (since) return since.value;
  if (!hasStorage()) return null;
  const now = Date.now();
  let prev: string | null = null;
  let cur: string | null = null;
  try {
    const o = JSON.parse(window.localStorage.getItem(VISIT_KEY) ?? "null") as { prev?: string | null; cur?: string | null } | null;
    prev = typeof o?.prev === "string" ? o.prev : null;
    cur = typeof o?.cur === "string" ? o.cur : null;
  } catch { /* 망가진 값은 처음 온 것으로 */ }
  // 마지막으로 연 때가 30분보다 오래되면 그것이 '지난번', 아니면 같은 방문이라 지난번을 그대로 둔다
  const curMs = cur ? Date.parse(cur) : NaN;
  const nextPrev = !Number.isNaN(curMs) && now - curMs > SESSION_MS ? cur : prev;
  try { window.localStorage.setItem(VISIT_KEY, JSON.stringify({ prev: nextPrev, cur: new Date(now).toISOString() })); } catch { /* 넘긴다 */ }
  since = { value: nextPrev };
  return nextPrev;
}

const noop = () => () => {};
export const subscribeNothing = noop;
