import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { cookies } from "next/headers";
import { LoginForm } from "@/components/login-form";
import { t } from "@/lib/i18n";
import { getLocale } from "@/lib/locale";
import { afterLogin, safeNext } from "@/lib/reader";
import { SESSION_COOKIE, readSession } from "@/lib/session";

export async function generateMetadata(): Promise<Metadata> {
  return { title: t(await getLocale(), "pg_login_doc_title") };
}

export default async function LoginPage({ searchParams }: { searchParams: Promise<{ next?: string; error?: string }> }) {
  const locale = await getLocale();
  const sp = await searchParams;
  // 같은 사이트 경로만 받는다(열린 리다이렉트 방지). 없으면 계정에 맞게: 검수자는 관리 화면, 그 밖은 첫 화면 —
  // 예전에는 누구나 /admin 으로 보내 일반 계정이 로그인마다 '권한 없음' 에 떨어졌다(2026-09-29 검토).
  const next = safeNext(sp.next);
  const session = await readSession((await cookies()).get(SESSION_COOKIE)?.value, process.env.SESSION_SECRET ?? "");
  if (session) redirect(afterLogin(next, session.reviewer));

  return (
    // 앱 틀 안의 가운데 작은 패널(docs/트렌드/디자인-개편.md '페이지'). 휴대폰은 테두리 없이 전폭
    <main id="main" className="flex flex-1 items-start justify-center px-4 pt-6 pb-12 sm:pt-12">
      <div className="w-full max-w-[400px] sm:rounded-lg sm:border sm:border-hairline sm:p-8">
        <h1 className="text-[24px] leading-[1.3] font-semibold text-ink">{t(locale, "login_title")}</h1>
        <p className="mt-2 mb-6 text-[14px] leading-[1.55] text-charcoal">{t(locale, "login_intro")}</p>
        <LoginForm locale={locale} next={next} initialError={sp.error ?? null} />
        <div className="mt-6 space-y-2 border-t border-hairline pt-4 text-[13px] leading-[1.55]">
          <p className="text-steel">{t(locale, "pg_login_help")}</p>
          <Link href="/" className="text-link-blue hover:underline">{t(locale, "login_back")}</Link>
        </div>
      </div>
    </main>
  );
}
