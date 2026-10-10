import { apiFetch } from "@/lib/api-fetch";
import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { isSampleMode } from "@/lib/data";
import { SESSION_COOKIE, readSession } from "@/lib/session";

/** 관리 화면 'Gemma 수동 실행'의 GPU 상태 – 검수자만. 데모 전에 GPU 를 켠 뒤 모델이 올라갔는지 본다. 모델은 부르지 않는다. */
export async function GET() {
  const session = await readSession((await cookies()).get(SESSION_COOKIE)?.value, process.env.SESSION_SECRET ?? "");
  if (!session) return NextResponse.json({ error: "login" }, { status: 401 });
  if (!session.reviewer) return NextResponse.json({ error: "reviewer" }, { status: 403 });
  // 예시 데이터 모드에는 GPU 도 백엔드도 없다
  if (isSampleMode) return NextResponse.json({ configured: false, ready: false, model: null });
  const token = process.env.FRONTEND_API_TOKEN;
  if (!token) return NextResponse.json({ error: "config" }, { status: 500 });
  try {
    const res = await apiFetch("/gpu/status", { headers: { "x-frontend-token": token }, cache: "no-store", signal: AbortSignal.timeout(10_000) });
    if (!res.ok) return NextResponse.json({ error: "failed" }, { status: 502 });
    return NextResponse.json(await res.json(), { headers: { "cache-control": "private, no-store" } });
  } catch {
    return NextResponse.json({ error: "failed" }, { status: 502 });
  }
}
