import Link from "next/link";
import { redirect } from "next/navigation";
import { cookies } from "next/headers";
import { LoginForm } from "@/components/login-form";
import { t } from "@/lib/i18n";
import { getLocale } from "@/lib/locale";
import { SESSION_COOKIE, readSession } from "@/lib/session";

export default async function LoginPage({ searchParams }: { searchParams: Promise<{ next?: string }> }) {
  const locale = await getLocale();
  const sp = await searchParams;
  // 열린 리다이렉트를 막는다 — 같은 사이트의 /admin 아래로만 보낸다
  const next = sp.next && /^\/admin(\/|$)/.test(sp.next) ? sp.next : "/admin";
  if (await readSession((await cookies()).get(SESSION_COOKIE)?.value, process.env.SESSION_SECRET ?? "")) redirect(next);

  return (
    <main className="flex flex-1 items-start justify-center px-4 py-16 sm:py-24">
      <div className="w-full max-w-[352px]">
        <h1 className="text-[20px] font-semibold text-ink">{t(locale, "login_title")}</h1>
        <p className="mt-2 mb-8 text-[14px] leading-relaxed text-steel">{t(locale, "login_intro")}</p>
        <LoginForm locale={locale} next={next} />
        <div className="mt-8 border-t border-hairline pt-4">
          <Link href="/" className="text-[13px] text-steel hover:text-ink">{t(locale, "login_back")}</Link>
        </div>
      </div>
    </main>
  );
}
