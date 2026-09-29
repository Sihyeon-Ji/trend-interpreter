import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { SESSION_COOKIE, readSession } from "@/lib/session";

const API = process.env.TREND_API_URL ?? "http://localhost:8080";

/** 검수 결정을 백엔드에 기록한다. 브라우저는 백엔드를 직접 부르지 않는다 —
 *  로그인과 검수 권한을 여기서 확인하고, 쓰기 토큰은 서버에만 둔다. 결정한 사람 이름도 세션에서 가져온다. */
export async function POST(req: Request, { params }: { params: Promise<{ termId: string }> }) {
  const session = await readSession((await cookies()).get(SESSION_COOKIE)?.value, process.env.SESSION_SECRET ?? "");
  if (!session) return NextResponse.json({ error: "로그인이 필요합니다." }, { status: 401 });

  if (!session.reviewer) return NextResponse.json({ error: "이 계정에는 사전 검수 권한이 없습니다." }, { status: 403 });

  const token = process.env.FRONTEND_API_TOKEN;
  if (!token) return NextResponse.json({ error: "서버 설정이 빠졌습니다. 관리자에게 알려 주세요." }, { status: 500 });

  let decision = "";
  let meaningId: unknown = null;   // 검수자가 본 뜻 — 그사이 새 판이 생겼으면 백엔드가 409 로 막는다
  try {
    ({ decision = "", meaning_id: meaningId = null } = await req.json());
  } catch {
    return NextResponse.json({ error: "요청 형식이 잘못됐습니다." }, { status: 400 });
  }
  if (decision !== "approve" && decision !== "reject") {
    return NextResponse.json({ error: "결정은 승인 또는 제외만 기록합니다." }, { status: 400 });
  }

  if (meaningId !== null && typeof meaningId !== "string") {
    return NextResponse.json({ error: "요청 형식이 잘못됐습니다." }, { status: 400 });
  }

  const { termId } = await params;
  let res: Response;
  try {
    res = await fetch(`${API}/review/${encodeURIComponent(termId)}`, {
      method: "POST",
      headers: { "content-type": "application/json", "x-frontend-token": token },
      body: JSON.stringify({ decision, by: session.user, meaning_id: meaningId }),
      cache: "no-store",
    });
  } catch {
    return NextResponse.json({ error: "서버에 연결하지 못했습니다." }, { status: 502 });
  }
  if (res.status === 409) return NextResponse.json({ error: "그사이 제안이 바뀌었습니다. 다시 보고 결정하세요." }, { status: 409 });
  if (!res.ok) return NextResponse.json({ error: `기록하지 못했습니다 (${res.status}).` }, { status: res.status });
  return NextResponse.json(await res.json());
}
