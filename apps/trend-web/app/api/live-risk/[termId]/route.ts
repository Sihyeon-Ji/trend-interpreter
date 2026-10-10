import { apiFetch } from "@/lib/api-fetch";
import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { isSampleMode } from "@/lib/data";
import { SESSION_COOKIE, readSession } from "@/lib/session";

/** 사전 항목의 '지금 다시 분류해 보기' – 검수자만(10-10 결정). 브라우저는 백엔드를 직접 부르지 않는다:
 *  세션과 검수 권한을 여기서 확인하고, 서버만 아는 토큰을 붙여 넘긴다. GPU 가 꺼져 있으면 백엔드가 곧바로 not_ready 를 준다. */
export async function POST(_req: Request, { params }: { params: Promise<{ termId: string }> }) {
  const session = await readSession((await cookies()).get(SESSION_COOKIE)?.value, process.env.SESSION_SECRET ?? "");
  if (!session) return NextResponse.json({ error: "login" }, { status: 401 });
  if (!session.reviewer) return NextResponse.json({ error: "reviewer" }, { status: 403 });
  const { termId } = await params;
  // 예시 데이터 모드에는 GPU 도 백엔드도 없다 – 운영에서 GPU 가 꺼진 때와 같은 답
  if (isSampleMode) return NextResponse.json({ status: "not_ready", term_id: termId, level: null, reasons: [], batch_level: null, batch_reasons: [],
    same_as_batch: null, sentences: [], found: 0, model: null, seconds: null, checked_at: null, cached: false });
  const token = process.env.FRONTEND_API_TOKEN;
  if (!token) return NextResponse.json({ error: "config" }, { status: 500 });
  try {
    const res = await apiFetch(`/terms/${encodeURIComponent(termId)}/live-risk`, {
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
