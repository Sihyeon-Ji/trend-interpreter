"use client";

import { useEffect, useState, useSyncExternalStore } from "react";

/* 처음 한 번만 트는 움직임 — 같은 결과를 다시 펼칠 때마다 조립 장면을 되풀이하지 않는다(무엇이 바뀌었을 때만 움직인다). */
const played = new Set<string>();

export function useFirstPlay(key: string): boolean {
  const [first] = useState(() => !played.has(key));
  useEffect(() => {
    played.add(key);
  }, [key]);
  return first;
}

const noop = () => () => {};
/** 서버 그림·하이드레이션 중에는 false — 저장된 초안을 되살리기 전에 '초안 없음' 을 잠깐 보이지 않게 */
export function useHydrated(): boolean {
  return useSyncExternalStore(noop, () => true, () => false);
}

/** 기다리는 동안 몇 초째인지 — 멈춘 것이 아님을 알린다(1초마다, 값은 타이머에서만 읽는다) */
export function useElapsed(sinceIso: string | null | undefined, on: boolean): number {
  const [sec, setSec] = useState(0);
  useEffect(() => {
    if (!on || !sinceIso) return;
    const since = Date.parse(sinceIso);
    const tick = () => setSec(Math.max(0, Math.round((Date.now() - since) / 1000)));
    const id = setInterval(tick, 1000);
    const first = setTimeout(tick, 0);
    return () => { clearInterval(id); clearTimeout(first); };
  }, [sinceIso, on]);
  return on ? sec : 0;
}
