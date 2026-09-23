import { cookies } from "next/headers";
import { PageShell } from "@/components/page-shell";
import { AdminNav } from "@/components/admin-nav";
import { SignOut } from "@/components/sign-out";
import { t } from "@/lib/i18n";
import { getLocale } from "@/lib/locale";
import { SESSION_COOKIE, readSession } from "@/lib/session";

export const metadata = { title: "관리 · 트렌드 통역" };

export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  const locale = await getLocale();
  // 여기까지 왔다는 건 미들웨어를 통과했다는 뜻이다. 이름은 누가 결정을 남기는지 보여 주려고 읽는다.
  const session = await readSession((await cookies()).get(SESSION_COOKIE)?.value, process.env.SESSION_SECRET ?? "");
  return (
    <PageShell>
    <div className="space-y-6">
      <header>
        <div className="flex items-baseline justify-between gap-4">
          <h1 className="text-[24px] font-semibold text-ink">관리</h1>
          <div className="flex items-baseline gap-3 whitespace-nowrap">
            {session && <span className="text-[13px] text-steel">{t(locale, "admin_signed_in_as")} {session.user}</span>}
            <SignOut label={t(locale, "admin_sign_out")} />
          </div>
        </div>
        <AdminNav />
      </header>
      {children}
    </div>
    </PageShell>
  );
}
