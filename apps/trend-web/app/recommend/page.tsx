import { PageShell } from "@/components/page-shell";
import { RecommendForm } from "@/components/recommend-form";
import { t } from "@/lib/i18n";
import { getLocale } from "@/lib/locale";
import { TARGET_REGIONS } from "@/lib/reader";
import { getReader } from "@/lib/reader-server";

/* 사용 흐름 2단계 '추천받기' (ADR 0001, Plan 07). 사진·문구 → 제품 설명 → 규칙 순위 → 어울리는 이유. */
export default async function RecommendPage() {
  const [locale, reader] = await Promise.all([getLocale(), getReader()]);
  // 로그인한 사람은 계정의 나라가 기본값, 익명은 한국 (목표 지역 밖 나라면 한국)
  const initial = reader.region && TARGET_REGIONS.includes(reader.region) ? [reader.region] : ["KR"];
  return (
    <PageShell>
      <div className="space-y-6">
        <header>
          <h1 className="text-[24px] font-semibold text-ink">{t(locale, "rec_title")}</h1>
          <p className="mt-1 max-w-[640px] text-[15px] text-charcoal">{t(locale, "rec_intro")}</p>
        </header>
        <RecommendForm locale={locale} initialRegions={initial} />
      </div>
    </PageShell>
  );
}
