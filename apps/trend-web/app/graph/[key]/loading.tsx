import { PageHeader } from "@/components/page-header";
import { PageShell } from "@/components/page-shell";
import { t } from "@/lib/i18n";
import { getLocale } from "@/lib/locale";

export default async function Loading() {
  const locale = await getLocale();
  return (
    <PageShell>
      <PageHeader title={<span role="status">{t(locale, "graph_loading")}</span>} />
    </PageShell>
  );
}
