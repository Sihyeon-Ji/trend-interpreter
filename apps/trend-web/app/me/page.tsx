import Link from "next/link";
import { PageHeader } from "@/components/page-header";
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
    <PageShell width="narrow">
      <div className="space-y-6">
        <PageHeader title={t(locale, "me_title")} description={t(locale, "me_intro")}
          meta={viewer ? <span className="text-charcoal">{viewer.user}</span> : undefined}
          actions={<SignOut label={t(locale, "admin_sign_out")} />}>
          {sp.denied === "review" && (
            <p role="alert" className="rounded-md border border-hairline-strong px-3 py-2 text-[14px] text-charcoal">{t(locale, "me_denied_review")}</p>
          )}
        </PageHeader>
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
