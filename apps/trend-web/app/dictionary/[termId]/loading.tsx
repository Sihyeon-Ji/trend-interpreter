import Link from "next/link";
import { PageHeader } from "@/components/page-header";
import { PageShell } from "@/components/page-shell";
import { t } from "@/lib/i18n";
import { getLocale } from "@/lib/locale";

/* 대시보드 행을 누르면 바로 반응하게 — 경로와 '불러오는 중' 한 줄만(빈 뼈대 칸을 채우지 않는다). */
export default async function Loading() {
  const locale = await getLocale();
  return (
    <PageShell>
      <PageHeader crumbs={<Link href="/dictionary" className="hover:text-ink hover:underline">{t(locale, "dict_title")}</Link>}
        title={<span role="status">{t(locale, "term_loading")}</span>} />
    </PageShell>
  );
}
