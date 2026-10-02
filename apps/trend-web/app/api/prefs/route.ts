import { apiFetch } from "@/lib/api-fetch";
import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { parseReader, type Reader } from "@/lib/reader";
import { SESSION_COOKIE, readSession } from "@/lib/session";

const SAMPLE = process.env.DATA_MODE !== "api";

async function session() {
  return readSession((await cookies()).get(SESSION_COOKIE)?.value, process.env.SESSION_SECRET ?? "");
}

/* 오류는 코드로만 돌려준다(signed_out·sample·not_configured·bad_request·unreachable·failed) — 문구는 화면이 두 언어로 붙인다. */
const fail = (code: string, status: number) => NextResponse.json({ code }, { status });

/** 내 설정 저장. 브라우저는 백엔드를 직접 부르지 않는다 — 여기서 로그인을 확인하고 누구의 설정인지 정한다. */
export async function PUT(req: Request) {
  const s = await session();
  if (!s) return fail("signed_out", 401);
  const token = process.env.FRONTEND_API_TOKEN;
  if (!token) {
    console.error("prefs: FRONTEND_API_TOKEN 이 없습니다");
    return fail(SAMPLE ? "sample" : "not_configured", 500);
  }

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return fail("bad_request", 400);
  }
  // 값은 화이트리스트로 한 번 거른다 — 브라우저가 보낸 것을 그대로 저장하지 않는다
  const prefs: Reader = parseReader(JSON.stringify(body));

  let res: Response;
  try {
    res = await apiFetch(`/prefs/${encodeURIComponent(s.user)}`, {
      method: "PUT",
      headers: { "content-type": "application/json", "x-frontend-token": token },
      body: JSON.stringify({ prefs }),
      cache: "no-store",
    });
  } catch {
    return fail("unreachable", 502);
  }
  if (!res.ok) {
    console.error(`prefs: 백엔드 PUT /prefs → ${res.status}`);   // 상태 번호는 로그에만
    return fail("failed", 502);
  }
  return NextResponse.json({ ok: true, prefs });
}
