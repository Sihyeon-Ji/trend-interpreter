import { PageShell } from "@/components/page-shell";
import { DictionaryList } from "@/components/dictionary-list";
import { getMeta, getTermRecords } from "@/lib/data";
import { t } from "@/lib/i18n";
import { getLocale } from "@/lib/locale";
import { getReader } from "@/lib/reader-server";

export default async function DictionaryPage() {
  const [records, locale, reader, meta] = await Promise.all([getTermRecords(), getLocale(), getReader(), getMeta()]);
  return (
    <PageShell>
    <div className="space-y-6">
      <header>
        <h1 className="text-[24px] font-semibold text-ink">{t(locale, "dict_title")}</h1>
        <p className="mt-1 text-[15px] text-charcoal">{t(locale, "dict_intro")}</p>
      </header>
      <DictionaryList records={records} locale={locale} readerGen={reader.gen ?? null} updatedAt={meta?.last_run ?? null} />
    </div>
    </PageShell>
  );
}
