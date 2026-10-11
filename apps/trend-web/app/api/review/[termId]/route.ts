import { apiFetch } from "@/lib/api-fetch";
import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { reviewDecision } from "@/lib/review-decision";
import { SESSION_COOKIE, readSession } from "@/lib/session";

/** 검수 결정을 백엔드에 기록한다. 브라우저는 백엔드를 직접 부르지 않는다 —
 *  로그인과 검수 권한을 여기서 확인하고, 쓰기 토큰은 서버에만 둔다. 결정한 사람 이름도 세션에서 가져온다.
 *  본문(결정·본 뜻·제안 종류·제안의 표·고른 문서)은 lib/review-decision.ts 가 거른 모양 그대로 넘긴다. */
export async function POST(req: Request, { params }: { params: Promise<{ termId: string }> }) {
  const session = await readSession((await cookies()).get(SESSION_COOKIE)?.value, process.env.SESSION_SECRET ?? "");
  if (!session) return NextResponse.json({ error: "로그인이 필요합니다." }, { status: 401 });

  if (!session.reviewer) return NextResponse.json({ error: "이 계정에는 사전 검수 권한이 없습니다." }, { status: 403 });
  if (session.readOnly) return NextResponse.json({ error: "읽기 전용 계정은 결정할 수 없습니다.", code: "readonly" }, { status: 403 });

  const token = process.env.FRONTEND_API_TOKEN;
  if (!token) return NextResponse.json({ error: "서버 설정이 빠졌습니다. 관리자에게 알려 주세요." }, { status: 500 });

  let raw: unknown;
  try {
    raw = await req.json();
  } catch {
    return NextResponse.json({ error: "요청 형식이 잘못됐습니다." }, { status: 400 });
  }
  const parsed = reviewDecision(raw);
  if (!parsed.ok) return NextResponse.json({ error: parsed.error }, { status: 400 });

  const { termId } = await params;
  let res: Response;
  try {
    res = await apiFetch(`/review/${encodeURIComponent(termId)}`, {
      method: "POST",
      headers: { "content-type": "application/json", "x-frontend-token": token },
      body: JSON.stringify({ ...parsed.body, by: session.user }),
      cache: "no-store",
    });
  } catch {
    return NextResponse.json({ error: "서버에 연결하지 못했습니다." }, { status: 502 });
  }
  if (res.status === 409) return NextResponse.json({ error: "그사이 제안이 바뀌었습니다. 다시 보고 결정하세요." }, { status: 409 });
  if (!res.ok) return NextResponse.json({ error: `기록하지 못했습니다 (${res.status}).` }, { status: res.status });
  return NextResponse.json(await res.json());
}
