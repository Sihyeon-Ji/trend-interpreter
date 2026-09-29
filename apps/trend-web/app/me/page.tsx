import type { Metadata } from "next";
import Link from "next/link";
import { PageHeader } from "@/components/page-header";
import { PageShell } from "@/components/page-shell";
import { ForgetQuery, ReaderForm } from "@/components/reader-form";
import { SignOut } from "@/components/sign-out";
import { isSampleMode } from "@/lib/data";
import { t } from "@/lib/i18n";
import { getLocale } from "@/lib/locale";
import { getViewer, loadReader } from "@/lib/reader-server";

export async function generateMetadata(): Promise<Metadata> {
  return { title: t(await getLocale(), "pg_me_doc_title") };
}

const notice = "rounded-lg border border-hairline-strong px-4 py-3 text-[14px] leading-[1.55] text-ink";

export default async function MePage({ searchParams }: { searchParams: Promise<{ denied?: string }> }) {
  const locale = await getLocale();
  const [{ reader, ok }, viewer, sp] = await Promise.all([loadReader(), getViewer(), searchParams]);
  // 예시 모드는 저장하지 않고, 저장된 값을 못 읽었으면 빈 값으로 덮어쓰지 않게 칸을 잠근다
  const locked = isSampleMode || !ok;
  return (
    <PageShell width="narrow">
      <div className="space-y-8">
        <PageHeader title={t(locale, "me_title")} description={t(locale, "me_intro")} />
        {sp.denied === "review" && (
          <>
            <p role="alert" className={notice}>{t(locale, "me_denied_review")}</p>
            <ForgetQuery path="/me" />
          </>
        )}
        {isSampleMode ? <p role="status" className={notice}>{t(locale, "pg_me_sample")}</p>
          : !ok && <p role="alert" className={notice}>{t(locale, "pg_me_load_failed")}</p>}
        <ReaderForm initial={reader} locale={locale} locked={locked}
          account={viewer && (
            <section aria-labelledby="me-account" className="space-y-4 border-t border-hairline pt-8">
              <h2 id="me-account" className="text-[18px] font-semibold text-ink">{t(locale, "pg_me_account")}</h2>
              <dl className="grid grid-cols-[112px_1fr] gap-x-4 gap-y-2 text-[14px]">
                <dt className="text-steel">{t(locale, "login_user")}</dt>
                <dd className="min-w-0 break-all text-ink">{viewer.user}</dd>
                {viewer.reviewer && (
                  <>
                    <dt className="text-steel">{t(locale, "pg_me_admin")}</dt>
                    <dd><Link href="/admin" className="text-link-blue hover:underline">{t(locale, "pg_me_open_admin")}</Link></dd>
                  </>
                )}
              </dl>
              <SignOut variant="button" label={t(locale, "admin_sign_out")} errorText={t(locale, "pg_me_sign_out_failed")} />
            </section>
          )} />
      </div>
    </PageShell>
  );
}
