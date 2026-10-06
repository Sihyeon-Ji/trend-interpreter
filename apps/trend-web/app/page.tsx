import type { Metadata } from "next";
import { MakeFlow } from "@/components/make-flow";
import { PageHeader } from "@/components/page-header";
import { PageShell } from "@/components/page-shell";
import { StatusBadge } from "@/components/status-badge";
import { isSampleMode } from "@/lib/data";
import { t } from "@/lib/i18n";
import { getLocale } from "@/lib/locale";
import { TARGET_REGIONS } from "@/lib/reader";
import { getReader } from "@/lib/reader-server";

// 탭·화면 낭독기가 화면을 가를 수 있게 화면마다 제목을 둔다
export async function generateMetadata(): Promise<Metadata> {
  const locale = await getLocale();
  return { title: `${t(locale, "make_page_title")} — ${t(locale, "site")}` };
}

/* 첫 화면 — 만들기 (Plan 20). 마케터가 제품과 시장을 넣으면 시장마다 그 나라에서 지금 쓰이는 밈으로 초안을 만들고 다시 검사한다.
   트렌드는 여기서 펼치지 않는다(둘러보기 /trends). 시장 기본값은 ?regions= → 로그인한 사람의 나라 → 한국·일본. 익명은 설정을 갖지 않는다. */
export default async function MakePage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const [locale, sp] = await Promise.all([getLocale(), searchParams]);
  const asked = [sp.regions].flat().filter(Boolean).join(",").split(",").map((s) => s.trim().toUpperCase()).filter((r) => TARGET_REGIONS.includes(r));
  const reader = asked.length ? {} : await getReader();
  const markets = asked.length ? asked.slice(0, 3)
    : reader.region && TARGET_REGIONS.includes(reader.region) ? [...new Set([reader.region, "KR", "JP"])].slice(0, 2) : ["KR", "JP"];
  return (
    <PageShell>
      <div className="space-y-8">
        <PageHeader title={t(locale, "make_page_title")} description={t(locale, "make_intro")} divider={false}
          meta={isSampleMode ? <StatusBadge tone="muted">{t(locale, "dash_sample_badge")}</StatusBadge> : null} />
        <MakeFlow key={locale} locale={locale} initialMarkets={markets} sample={isSampleMode} />
      </div>
    </PageShell>
  );
}
