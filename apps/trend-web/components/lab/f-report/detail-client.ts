"use client";

import { useSyncExternalStore } from "react";
import type { TermDetail } from "@/lib/lab/f-report-detail";

/* 미리보기·지켜보기가 나중에 받는 항목 요약 — 같은 사이트의 읽기 전용 라우트에서. 약속을 id 마다 한 번만 만들어 use() 로 읽는다. */
const promises = new Map<string, Promise<TermDetail | null>>();
export function loadDetail(id: string, locale: string): Promise<TermDetail | null> {
  const key = `${locale}:${id}`;
  let p = promises.get(key);
  if (!p) {
    p = fetch(`/lab/f-report/api/term/${encodeURIComponent(id)}?locale=${locale}`).then((r) => (r.ok ? (r.json() as Promise<TermDetail>) : null)).catch(() => null);
    promises.set(key, p);
  }
  return p;
}

const noop = () => () => {};
/** 서버 렌더에서는 요약을 부르지 않는다(상대 주소 fetch 불가) — 물을 붙인 뒤에만 */
export const useMounted = () => useSyncExternalStore(noop, () => true, () => false);
