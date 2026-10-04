import type { Metadata } from "next";
import { Suspense } from "react";
import { DictionaryChat } from "@/components/dictionary-chat";
import { ExplainCards, ResultHeader, foundSummary } from "@/components/explain-cards";
import { PageHeader } from "@/components/page-header";
import { PageShell } from "@/components/page-shell";
import { explain, getSampleCopy, isSampleMode } from "@/lib/data";
import { t, type Locale } from "@/lib/i18n";
import { getLocale } from "@/lib/locale";
import { getReader } from "@/lib/reader-server";

/** 미리 풀어 둔 예시 댓글. 머리와 입력은 먼저 그리고 이것만 따로 기다린다 — 서버의 재작성을 기다리느라 입력 칸까지 늦게 뜨던 것.
 *  실패하면 예시만 뺀다: 사용자가 요청한 것이 아니므로 오류를 알리지 않는다. */
async function ExampleResult({ locale, text }: { locale: Locale; text: string }) {
  const result = await explain(text, locale, await getReader()).catch(() => null);
  if (!result?.items.length) return null;
  return (
    <section aria-labelledby="example-heading" className="space-y-4">
      <ResultHeader locale={locale} sample headingId="example-heading" summary={foundSummary(locale, result.items.length)} />
      <ExplainCards result={result} locale={locale} original={text} />
    </section>
  );
}

// 탭·화면 낭독기가 화면을 가를 수 있게 화면마다 제목을 둔다 — 여러 화면이 사이트 이름 하나뿐이었다(10-04)
export async function generateMetadata(): Promise<Metadata> {
  const locale = await getLocale();
  return { title: `${t(locale, "home_title")} — ${t(locale, "site")}` };
}

export default async function ExplainPage() {
  const locale = await getLocale();
  const text = getSampleCopy(locale);
  return (
    <PageShell width="narrow">
      <div className="space-y-6">
        {/* 제목은 메뉴 이름과 같다(예전에는 메뉴 '메시지 해석', 제목 '사전에 묻기' 로 이름이 둘이었다) */}
        <PageHeader title={t(locale, "home_title")} description={t(locale, "home_intro")} />
        <DictionaryChat locale={locale} sample={isSampleMode} sampleText={text}
          example={
            <Suspense fallback={<p className="text-[14px] text-steel">{t(locale, "pg_ex_example_loading")}</p>}>
              <ExampleResult locale={locale} text={text} />
            </Suspense>
          } />
      </div>
    </PageShell>
  );
}
