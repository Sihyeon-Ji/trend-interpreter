import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { parseReader, type Reader } from "@/lib/reader";
import { SESSION_COOKIE, readSession } from "@/lib/session";

const API = process.env.TREND_API_URL ?? "http://localhost:8080";

async function session() {
  return readSession((await cookies()).get(SESSION_COOKIE)?.value, process.env.SESSION_SECRET ?? "");
}

/** 내 설정 저장. 브라우저는 백엔드를 직접 부르지 않는다 — 여기서 로그인을 확인하고 누구의 설정인지 정한다. */
export async function PUT(req: Request) {
  const s = await session();
  if (!s) return NextResponse.json({ error: "로그인이 필요합니다." }, { status: 401 });
  const token = process.env.FRONTEND_API_TOKEN;
  if (!token) return NextResponse.json({ error: "서버 설정이 빠졌습니다. 관리자에게 알려 주세요." }, { status: 500 });

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "요청 형식이 잘못됐습니다." }, { status: 400 });
  }
  // 값은 화이트리스트로 한 번 거른다 — 브라우저가 보낸 것을 그대로 저장하지 않는다
  const prefs: Reader = parseReader(JSON.stringify(body));

  let res: Response;
  try {
    res = await fetch(`${API}/prefs/${encodeURIComponent(s.user)}`, {
      method: "PUT",
      headers: { "content-type": "application/json", "x-frontend-token": token },
      body: JSON.stringify({ prefs }),
      cache: "no-store",
    });
  } catch {
    return NextResponse.json({ error: "서버에 연결하지 못했습니다." }, { status: 502 });
  }
  if (!res.ok) return NextResponse.json({ error: `저장하지 못했습니다 (${res.status}).` }, { status: res.status });
  return NextResponse.json({ ok: true, prefs });
}
