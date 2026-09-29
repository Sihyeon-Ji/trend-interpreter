import { PageHeader } from "@/components/page-header";
import { PageShell } from "@/components/page-shell";
import { DictionaryChat } from "@/components/dictionary-chat";
import { explain, getSampleCopy } from "@/lib/data";
import { t } from "@/lib/i18n";
import { getLocale } from "@/lib/locale";
import { getReader } from "@/lib/reader-server";

export default async function ExplainPage() {
  const locale = await getLocale();
  const text = getSampleCopy(locale);
  const result = await explain(text, locale, await getReader());   // 첫 화면이 비어 있지 않게 예시 하나를 미리 풀어 둔다
  return (
    <PageShell width="narrow">
      <div className="space-y-6">
        <PageHeader title={t(locale, "chat_title")} description={t(locale, "home_intro")} />
        <DictionaryChat locale={locale} initial={{ text, result }} />
      </div>
    </PageShell>
  );
}
