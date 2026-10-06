import Link from "next/link";
import { getPublicationBatches, isSampleMode } from "@/lib/data";
import { getLocale } from "@/lib/locale";
import { t } from "@/lib/i18n";
import { fmtDateTime } from "@/lib/labels";

export default async function BatchesPage({ searchParams }: { searchParams: Promise<{ page?: string }> }) {
  const [locale, query] = await Promise.all([getLocale(), searchParams]);
  const page = /^\d{1,6}$/.test(query.page ?? "") ? Math.max(1, Number(query.page)) : 1;
  const { items, total } = await getPublicationBatches((page - 1) * 50);
  return <section className="space-y-5">
    <h2 className="text-lg font-semibold">{t(locale, "adm_tab_batches")}</h2>
    <p className="text-sm text-charcoal">{t(locale, "batch_intro")}</p>
    {isSampleMode && <p className="text-sm text-steel">{t(locale, "batch_sample")}</p>}
    {items.length === 0 ? <p>{t(locale, "batch_empty")}</p> : <ul className="divide-y divide-hairline">
      {items.map((item) => <li key={item.batch_id} className="flex flex-wrap justify-between gap-2 py-4">
        <Link href={`/admin/batches/${encodeURIComponent(item.batch_id)}`} className="break-all text-link-blue hover:underline">{item.batch_id}</Link>
        <span className="text-sm">{t(locale, `batch_${item.status}`)} · {t(locale, "adm_count").replace("{n}", String(item.item_count))} · {fmtDateTime(item.created_at, locale)}</span>
      </li>)}
    </ul>}
    <nav className="flex gap-4" aria-label={t(locale, "adm_tab_batches")}>
      {page > 1 && <Link href={`/admin/batches?page=${page - 1}`}>{t(locale, "batch_prev")}</Link>}
      {page * 50 < total && <Link href={`/admin/batches?page=${page + 1}`}>{t(locale, "batch_next")}</Link>}
    </nav>
  </section>;
}
