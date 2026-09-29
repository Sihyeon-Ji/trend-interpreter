import Link from "next/link";
import { PageHeader } from "@/components/page-header";
import { PageShell } from "@/components/page-shell";
import { StatePanel } from "@/components/state-panel";
import { Button } from "@/components/ui/button";
import { t } from "@/lib/i18n";
import { getLocale } from "@/lib/locale";

/* 사전에 없는 말(서버가 404 라고 한 것만). 물어보면 조사 목록에 오른다는 다음 할 일을 알린다. */
export default async function TermNotFound() {
  const locale = await getLocale();
  return (
    <PageShell>
      <div className="space-y-6">
        <PageHeader crumbs={<Link href="/dictionary" className="hover:text-ink hover:underline">{t(locale, "dict_title")}</Link>}
          title={t(locale, "term_nf_title")} />
        <StatePanel action={
          <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
            <Button asChild variant="outline" className="h-10 rounded-md border-hairline-strong px-4 text-[14px] shadow-none"><Link href="/explain">{t(locale, "term_nf_explain")}</Link></Button>
            <Link href="/dictionary" className="text-[14px] text-link-blue hover:underline">{t(locale, "term_nf_list")}</Link>
          </div>
        }>{t(locale, "term_nf_body")}</StatePanel>
      </div>
    </PageShell>
  );
}
