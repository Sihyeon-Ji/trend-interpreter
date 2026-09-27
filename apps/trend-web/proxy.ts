import { NextResponse, type NextRequest } from "next/server";
import { SESSION_COOKIE, readSession } from "@/lib/session";

/** 지도·사전·메시지 해석은 로그인 없이 그대로 연다.
 *  `/me`(내 설정)는 로그인한 사람만, `/admin`(사전 검수)은 그중 검수자만. */
export async function middleware(req: NextRequest) {
  const session = await readSession(req.cookies.get(SESSION_COOKIE)?.value, process.env.SESSION_SECRET ?? "");
  const path = req.nextUrl.pathname;

  if (!session) {
    const login = new URL("/login", req.url);
    login.searchParams.set("next", path + req.nextUrl.search);
    return NextResponse.redirect(login);
  }
  if (path.startsWith("/admin") && !session.reviewer) {
    return NextResponse.redirect(new URL("/me?denied=review", req.url));  // 로그인은 했지만 검수 권한이 없다
  }
  return NextResponse.next();
}

export const config = { matcher: ["/admin/:path*", "/me/:path*", "/me"] };
