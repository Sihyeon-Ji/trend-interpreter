import { apiFetch } from "@/lib/api-fetch";
import { NextResponse } from "next/server";
import { afterLogin, safeNext } from "@/lib/reader";
import { SESSION_COOKIE, SESSION_HOURS, signSession } from "@/lib/session";

const SAMPLE = process.env.DATA_MODE !== "api";

/** 화면이 i18n 으로 옮기는 오류 코드. 문구는 서버가 정하지 않는다 — 영어 화면에 한국어 오류가 나가던 것(2026-09-29 검토). */
type LoginCode = "not_configured" | "bad_request" | "missing_fields" | "unreachable" | "sample" | "bad_credentials" | "failed";

/** 자격 확인은 백엔드가 하고(나중에 Firebase Auth 로 교체), 브라우저 세션 쿠키는 여기서 만든다.
 *  쿠키가 화면과 같은 출처에 있어야 /admin 미들웨어가 읽을 수 있다.
 *  JSON(화면의 스크립트)과 폼 전송(스크립트가 붙기 전에 누른 Enter) 둘 다 받는다 — 폼 전송이면 303 으로 돌려보낸다. */
export async function POST(req: Request) {
  const isForm = !(req.headers.get("content-type") ?? "").includes("application/json");
  let user = "", password = "", next: string | null = null;
  try {
    if (isForm) {
      const f = await req.formData();
      user = String(f.get("username") ?? "");
      password = String(f.get("password") ?? "");
      next = safeNext(String(f.get("next") ?? ""));
    } else {
      ({ user = "", password = "" } = (await req.json()) as { user?: string; password?: string });
    }
  } catch {
    return fail("bad_request", 400);
  }

  // 폼 전송이 실패하면 로그인 화면으로 코드를 들고 돌아간다(비밀번호는 주소에 싣지 않는다)
  function fail(code: LoginCode, status: number) {
    if (!isForm) return NextResponse.json({ code }, { status });
    const q = new URLSearchParams({ error: code });
    if (next) q.set("next", next);
    return new NextResponse(null, { status: 303, headers: { location: `/login?${q}` } });
  }

  const secret = process.env.SESSION_SECRET;
  if (!secret) {
    console.error("login: SESSION_SECRET 이 없습니다");
    return fail(SAMPLE ? "sample" : "not_configured", 500);
  }
  if (!user.trim() || !password) return fail("missing_fields", 400);

  let res: Response;
  try {
    res = await apiFetch(`/auth/login`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ user, password }),
      cache: "no-store",
    });
  } catch {
    return fail(SAMPLE ? "sample" : "unreachable", 502);
  }
  if (res.status === 401) return fail("bad_credentials", 401);
  if (!res.ok) {
    console.error(`login: 백엔드 /auth/login → ${res.status}`);   // 상태 번호는 로그에만 남긴다
    return fail("failed", 502);
  }

  const { name, reviewer, readonly } = (await res.json()) as { name: string; reviewer?: boolean; readonly?: boolean };
  const out = isForm
    ? new NextResponse(null, { status: 303, headers: { location: afterLogin(next, !!reviewer) } })
    : NextResponse.json({ ok: true, name, reviewer: !!reviewer });
  // Secure 는 실제로 HTTPS 일 때만 붙인다. NODE_ENV 로 정하면 사내망 HTTP(예: http://192.168.x.x:3100)에서
  // 브라우저가 쿠키를 아예 저장하지 않아 "로그인은 되는데 로그인 상태가 안 남는" 증상이 된다(2026-09-16 실사고).
  // Cloud Run 은 TLS 를 앞단에서 끊고 x-forwarded-proto 를 붙여 주므로 배포판에서는 그대로 Secure 가 된다.
  const proto = req.headers.get("x-forwarded-proto")?.split(",")[0].trim() ?? new URL(req.url).protocol.replace(":", "");
  out.cookies.set(SESSION_COOKIE, await signSession(name, !!reviewer, secret, SESSION_HOURS, !!readonly), {
    httpOnly: true,
    sameSite: "lax",
    secure: proto === "https",
    path: "/",
    maxAge: SESSION_HOURS * 3600,
  });
  return out;
}
