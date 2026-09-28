import { NextResponse } from "next/server";
import { SESSION_COOKIE, SESSION_HOURS, signSession } from "@/lib/session";

const API = process.env.TREND_API_URL ?? "http://localhost:8080";

/** 자격 확인은 백엔드가 하고(나중에 Firebase Auth 로 교체), 브라우저 세션 쿠키는 여기서 만든다.
 *  쿠키가 화면과 같은 출처에 있어야 /admin 미들웨어가 읽을 수 있다. */
export async function POST(req: Request) {
  const secret = process.env.SESSION_SECRET;
  if (!secret) return NextResponse.json({ error: "서버에 세션 비밀값이 없습니다. 관리자에게 알려 주세요." }, { status: 500 });

  let user = "", password = "";
  try {
    ({ user = "", password = "" } = await req.json());
  } catch {
    return NextResponse.json({ error: "요청 형식이 잘못됐습니다." }, { status: 400 });
  }
  if (!user.trim() || !password) return NextResponse.json({ error: "아이디와 비밀번호를 모두 입력해 주세요." }, { status: 400 });

  let res: Response;
  try {
    res = await fetch(`${API}/auth/login`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ user, password }),
      cache: "no-store",
    });
  } catch {
    return NextResponse.json({ error: "서버에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요." }, { status: 502 });
  }
  if (res.status === 401) return NextResponse.json({ error: "아이디 또는 비밀번호가 맞지 않습니다." }, { status: 401 });
  if (!res.ok) return NextResponse.json({ error: `로그인에 실패했습니다 (${res.status}).` }, { status: 502 });

  const { name, reviewer } = (await res.json()) as { name: string; reviewer?: boolean };
  // Secure 는 실제로 HTTPS 일 때만 붙인다. NODE_ENV 로 정하면 사내망 HTTP(예: http://192.168.x.x:3100)에서
  // 브라우저가 쿠키를 아예 저장하지 않아 "로그인은 되는데 로그인 상태가 안 남는" 증상이 된다(2026-09-16 실사고).
  // Cloud Run 은 TLS 를 앞단에서 끊고 x-forwarded-proto 를 붙여 주므로 배포판에서는 그대로 Secure 가 된다.
  const proto = req.headers.get("x-forwarded-proto")?.split(",")[0].trim() ?? new URL(req.url).protocol.replace(":", "");
  const out = NextResponse.json({ ok: true, name, reviewer: !!reviewer });
  out.cookies.set(SESSION_COOKIE, await signSession(name, !!reviewer, secret), {
    httpOnly: true,
    sameSite: "lax",
    secure: proto === "https",
    path: "/",
    maxAge: SESSION_HOURS * 3600,
  });
  return out;
}
