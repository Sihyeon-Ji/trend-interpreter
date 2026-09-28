import { cookies } from "next/headers";
import { parseReader, type Reader } from "./reader";
import { SESSION_COOKIE, readSession } from "./session";

const API = process.env.TREND_API_URL ?? "http://localhost:8080";

/** 로그인한 사람의 설정. 익명이면 빈 값 — 설명이 중립으로 나가고 재작성 캐시도 하나로 모인다. */
export async function getReader(): Promise<Reader> {
  const s = await readSession((await cookies()).get(SESSION_COOKIE)?.value, process.env.SESSION_SECRET ?? "");
  const token = process.env.FRONTEND_API_TOKEN;
  if (!s || !token) return {};
  try {
    const res = await fetch(`${API}/prefs/${encodeURIComponent(s.user)}`, {
      headers: { "x-frontend-token": token },
      cache: "no-store",
    });
    if (!res.ok) return {};
    return parseReader(JSON.stringify(await res.json()));
  } catch {
    return {};   // 설정을 못 읽어도 화면은 중립으로 뜬다
  }
}

/** 로그인한 사람인지, 검수자인지 — 내비게이션과 설정 화면이 쓴다. */
export async function getViewer(): Promise<{ user: string; reviewer: boolean } | null> {
  const s = await readSession((await cookies()).get(SESSION_COOKIE)?.value, process.env.SESSION_SECRET ?? "");
  return s ? { user: s.user, reviewer: s.reviewer } : null;
}
