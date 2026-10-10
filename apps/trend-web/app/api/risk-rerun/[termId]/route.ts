import { apiFetch } from "@/lib/api-fetch";
import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { isSampleMode } from "@/lib/data";
import { SESSION_COOKIE, readSession } from "@/lib/session";

/** 관리 화면 '수동 실행'(Gemma 실시간 분류 2단계) – 검수자만. 배치 리스크 단계를 용어 하나에 다시 돌린 미리보기를 받아 온다.
 *  브라우저는 백엔드를 직접 부르지 않는다: 세션과 검수 권한을 여기서 확인하고, 서버만 아는 토큰을 붙여 넘긴다. */
export async function POST(_req: Request, { params }: { params: Promise<{ termId: string }> }) {
  const session = await readSession((await cookies()).get(SESSION_COOKIE)?.value, process.env.SESSION_SECRET ?? "");
  if (!session) return NextResponse.json({ error: "login" }, { status: 401 });
  if (!session.reviewer) return NextResponse.json({ error: "reviewer" }, { status: 403 });
  const { termId } = await params;
  // 예시 데이터 모드에는 GPU 도 백엔드도 없다 – 운영에서 GPU 가 꺼진 때와 같은 답
  if (isSampleMode) return NextResponse.json({ status: "not_ready", term_id: termId, stage: "risk", public_level: null, before_level: null,
    before_reasons: [], after_level: null, after_reasons: [], changed: 0, sentences: [], model: null, seconds: null, checked_at: null });
  const token = process.env.FRONTEND_API_TOKEN;
  if (!token) return NextResponse.json({ error: "config" }, { status: 500 });
  try {
    const res = await apiFetch(`/terms/${encodeURIComponent(termId)}/risk-rerun`, {
      method: "POST",
      headers: { "x-frontend-token": token },
      cache: "no-store",
      signal: AbortSignal.timeout(90_000),
    });
    if (!res.ok) return NextResponse.json({ error: "failed" }, { status: res.status === 404 ? 404 : 502 });
    return NextResponse.json(await res.json(), { headers: { "cache-control": "private, no-store" } });
  } catch {
    return NextResponse.json({ error: "failed" }, { status: 502 });
  }
}
