import { apiFetch } from "@/lib/api-fetch";
import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { SESSION_COOKIE, readSession } from "@/lib/session";

/** 검수자가 정한 리스크 수준을 백엔드에 기록한다. 권한 확인·쓰기 토큰은 뜻 검수(../route.ts)와 같다.
 *  level 이 null 이면 사람의 결정을 지우고 규칙 판정으로 돌아간다. */
export async function POST(req: Request, { params }: { params: Promise<{ termId: string }> }) {
  const session = await readSession((await cookies()).get(SESSION_COOKIE)?.value, process.env.SESSION_SECRET ?? "");
  if (!session) return NextResponse.json({ error: "로그인이 필요합니다." }, { status: 401 });

  if (!session.reviewer) return NextResponse.json({ error: "이 계정에는 사전 검수 권한이 없습니다." }, { status: 403 });

  const token = process.env.FRONTEND_API_TOKEN;
  if (!token) return NextResponse.json({ error: "서버 설정이 빠졌습니다. 관리자에게 알려 주세요." }, { status: 500 });

  let level: unknown;
  try {
    ({ level = null } = await req.json());
  } catch {
    return NextResponse.json({ error: "요청 형식이 잘못됐습니다." }, { status: 400 });
  }
  if (level !== null && level !== "none" && level !== "caution" && level !== "avoid") {
    return NextResponse.json({ error: "수준은 없음·주의·사용 자제 가운데 하나입니다." }, { status: 400 });
  }

  const { termId } = await params;
  let res: Response;
  try {
    res = await apiFetch(`/review/${encodeURIComponent(termId)}/risk`, {
      method: "POST",
      headers: { "content-type": "application/json", "x-frontend-token": token },
      body: JSON.stringify({ level, by: session.user }),   // 결정한 사람은 세션에서 — 검수 기록이 실제 계정이 된다
      cache: "no-store",
    });
  } catch {
    return NextResponse.json({ error: "서버에 연결하지 못했습니다." }, { status: 502 });
  }
  if (!res.ok) return NextResponse.json({ error: `기록하지 못했습니다 (${res.status}).` }, { status: res.status });
  return NextResponse.json(await res.json());
}
