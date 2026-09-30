import Link from "next/link";
import { PageHeader } from "@/components/page-header";
import { PageShell } from "@/components/page-shell";
import { StatePanel } from "@/components/state-panel";
import { t } from "@/lib/i18n";
import { getLocale } from "@/lib/locale";

export default async function GraphNotFound() {
  const locale = await getLocale();
  return (
    <PageShell>
      <div className="space-y-6">
        <PageHeader crumbs={<Link href="/graph" className="hover:text-ink hover:underline">{t(locale, "graph_back")}</Link>} title={t(locale, "graph_nf_title")} />
        <StatePanel action={<Link href="/graph" className="text-[14px] text-link-blue hover:underline">{t(locale, "graph_back")}</Link>}>{t(locale, "graph_nf_body")}</StatePanel>
      </div>
    </PageShell>
  );
}
