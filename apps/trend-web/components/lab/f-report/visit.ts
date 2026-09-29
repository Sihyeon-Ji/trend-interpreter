"use client";

import { useSyncExternalStore } from "react";

/* 지난 방문 — 브라우저에만 적는다. 익명은 서버에 설정을 갖지 않는다.
   localStorage fr:visit = { seen: 마지막으로 본 때, base: 그 전 방문 } — 30분 안의 재방문은 같은 방문으로 친다(새로 고침·항목에 다녀오기).
   sessionStorage fr:baseline = 이 탭이 '지난 방문' 으로 견주는 때 — 같은 탭에서는 새로 고쳐도 그대로라 표시가 사라지지 않는다. */
const KEY = "fr:visit";
const BASE = "fr:baseline";
const GRACE = 30 * 60_000;

export interface LastVisit { at: string | null; now: number }   // at: null = 처음. now: 이 탭에서 처음 읽은 때(그림이 흔들리지 않게 고정)
let baseline: LastVisit | undefined;
const noop = () => () => {};

function readVisit(): { seen: string; base: string | null } | null {
  try {
    const raw = window.localStorage.getItem(KEY);
    const v = raw ? (JSON.parse(raw) as { seen?: string; base?: string | null }) : null;
    return v && typeof v.seen === "string" && !Number.isNaN(Date.parse(v.seen)) ? { seen: v.seen, base: typeof v.base === "string" ? v.base : null } : null;
  } catch { return null; }
}
const writeVisit = (v: { seen: string; base: string | null }) => { try { window.localStorage.setItem(KEY, JSON.stringify(v)); } catch { /* 저장이 막힌 브라우저 */ } };

function snapshot(): LastVisit {
  if (baseline !== undefined) return baseline;
  const now = new Date();
  const v = readVisit();
  let base: string | null;
  if (!v) base = null;
  else if (now.getTime() - Date.parse(v.seen) > GRACE) base = v.seen;   // 30분 넘게 지났으면 지난번 본 때가 기준
  else base = v.base;                                                    // 같은 방문 안 — 기준은 그대로
  writeVisit({ seen: now.toISOString(), base });
  let tabBase: string | null | undefined;
  try { const s = window.sessionStorage.getItem(BASE); tabBase = s === null ? undefined : s === "none" ? null : s; } catch { tabBase = undefined; }
  if (tabBase === undefined) {
    tabBase = base;
    try { window.sessionStorage.setItem(BASE, base ?? "none"); } catch { /* 저장이 막힌 브라우저 */ }
  }
  baseline = { at: tabBase && !Number.isNaN(Date.parse(tabBase)) ? tabBase : null, now: now.getTime() };
  return baseline;
}

/** 지난 방문(없으면 at=null = 처음). 서버 그림과 하이드레이션 중에는 undefined. */
export function useLastVisit(): LastVisit | undefined {
  return useSyncExternalStore(noop, snapshot, () => undefined);
}
