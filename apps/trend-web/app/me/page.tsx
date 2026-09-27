import Link from "next/link";
import { PageShell } from "@/components/page-shell";
import { ReaderForm } from "@/components/reader-form";
import { SignOut } from "@/components/sign-out";
import { t } from "@/lib/i18n";
import { getLocale } from "@/lib/locale";
import { getReader, getViewer } from "@/lib/reader-server";

export default async function MePage({ searchParams }: { searchParams: Promise<{ denied?: string }> }) {
  const locale = await getLocale();
  const [reader, viewer, sp] = await Promise.all([getReader(), getViewer(), searchParams]);
  return (
    <PageShell>
      <div className="space-y-6">
        <header>
          <div className="flex items-baseline justify-between gap-4">
            <h1 className="text-[24px] font-semibold text-ink">{t(locale, "me_title")}</h1>
            <div className="flex items-baseline gap-3 whitespace-nowrap">
              {viewer && <span className="text-[13px] text-steel">{viewer.user}</span>}
              <SignOut label={t(locale, "admin_sign_out")} />
            </div>
          </div>
          <p className="mt-1 max-w-[560px] text-[15px] text-charcoal">{t(locale, "me_intro")}</p>
          {sp.denied === "review" && (
            <p role="alert" className="mt-3 border-l-2 border-hairline-strong pl-3 text-[14px] text-charcoal">{t(locale, "me_denied_review")}</p>
          )}
        </header>
        <ReaderForm initial={reader} locale={locale} />
        {viewer?.reviewer && (
          <p className="border-t border-hairline pt-4 text-[13px]">
            <Link href="/admin" className="text-steel hover:text-ink">{t(locale, "nav_admin")}</Link>
          </p>
        )}
      </div>
    </PageShell>
  );
}
