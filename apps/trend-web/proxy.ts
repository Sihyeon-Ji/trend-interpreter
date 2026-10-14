import { NextResponse, type NextRequest } from "next/server";
import { LOCALE_COOKIE, isLocale } from "@/lib/i18n";
import { SESSION_COOKIE, readSession } from "@/lib/session";

/** 지도·사전·메시지 해석은 로그인 없이 그대로 연다.
 *  `/me`(내 설정)는 로그인한 사람만, `/admin`(사전 검수)은 그중 검수자만.
 *  어느 주소든 `?lang=en|ko|ja` 가 붙으면 그 언어를 쿠키로 저장하고 붙이지 않은 주소로 다시 보낸다 — 제출 링크·공유 링크가 언어를 정한다(10-14). */
export async function proxy(req: NextRequest) {
  const lang = req.nextUrl.searchParams.get("lang");
  if (lang !== null) {
    const clean = req.nextUrl.clone();
    clean.searchParams.delete("lang");
    const res = NextResponse.redirect(clean);
    if (isLocale(lang)) res.cookies.set(LOCALE_COOKIE, lang, { path: "/", maxAge: 31536000, sameSite: "lax" });
    return res;
  }
  const path = req.nextUrl.pathname;
  if (!(path === "/me" || path.startsWith("/me/") || path.startsWith("/admin"))) return NextResponse.next();

  const session = await readSession(req.cookies.get(SESSION_COOKIE)?.value, process.env.SESSION_SECRET ?? "");

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

// 정적 파일·API 는 거치지 않는다
export const config = { matcher: ["/((?!_next/|api/|favicon|.*\\.[a-z0-9]+$).*)"] };
