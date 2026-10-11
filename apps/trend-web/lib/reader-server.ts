import { apiFetch } from "@/lib/api-fetch";
import { cookies } from "next/headers";
import { parseReader, type Reader } from "./reader";
import { SESSION_COOKIE, readSession } from "./session";

/** 로그인한 사람의 설정과, 저장된 값을 제대로 읽었는지. 내 설정 화면은 ok 가 아니면 칸을 잠근다 —
 *  못 읽은 것을 '설정 없음' 으로 보이면 한 칸만 고쳐 저장할 때 나머지 저장값이 빈 값으로 덮인다(2026-09-29 검토). */
export async function loadReader(): Promise<{ reader: Reader; ok: boolean }> {
  const s = await readSession((await cookies()).get(SESSION_COOKIE)?.value, process.env.SESSION_SECRET ?? "");
  if (!s) return { reader: {}, ok: true };
  const token = process.env.FRONTEND_API_TOKEN;
  if (!token) return { reader: {}, ok: false };
  try {
    const res = await apiFetch(`/prefs/${encodeURIComponent(s.user)}`, {
      headers: { "x-frontend-token": token },
      cache: "no-store",
    });
    if (!res.ok) return { reader: {}, ok: false };
    return { reader: parseReader(JSON.stringify(await res.json())), ok: true };
  } catch {
    return { reader: {}, ok: false };
  }
}

/** 로그인한 사람의 설정. 익명이면 빈 값 — 설명이 중립으로 나가고 재작성 캐시도 하나로 모인다.
 *  설정을 못 읽어도 화면은 중립으로 뜬다. */
export async function getReader(): Promise<Reader> {
  return (await loadReader()).reader;
}

/** 로그인한 사람인지, 검수자인지 — 내비게이션과 설정 화면이 쓴다. */
export async function getViewer(): Promise<{ user: string; reviewer: boolean; readOnly: boolean } | null> {
  const s = await readSession((await cookies()).get(SESSION_COOKIE)?.value, process.env.SESSION_SECRET ?? "");
  return s ? { user: s.user, reviewer: s.reviewer, readOnly: s.readOnly } : null;
}
