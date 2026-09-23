import { PageShell } from "@/components/page-shell";
import Link from "next/link";
import { t } from "@/lib/i18n";
import { getLocale } from "@/lib/locale";

export default async function NotFound() {
  const locale = await getLocale();
  return (
    <PageShell>
    <div className="py-16">
      <h1 className="text-[20px] font-semibold text-ink">{t(locale, "notfound_title")}</h1>
      <p className="mt-2 text-[15px] text-charcoal">{t(locale, "notfound_body")}</p>
      <Link href="/dictionary" className="mt-4 inline-block text-[14px] text-link-blue hover:underline">{t(locale, "notfound_back")}</Link>
    </div>
    </PageShell>
  );
}
