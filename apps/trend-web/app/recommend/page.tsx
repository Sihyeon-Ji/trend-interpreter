import { PageShell } from "@/components/page-shell";
import { RecommendForm } from "@/components/recommend-form";
import { t } from "@/lib/i18n";
import { getLocale } from "@/lib/locale";
import { TARGET_REGIONS } from "@/lib/reader";
import { getReader } from "@/lib/reader-server";

/* 사용 흐름 2단계 '추천받기' (ADR 0001, Plan 07). 사진·문구 → 제품 설명 → 규칙 순위 → 저장된 뜻·국가별 해석으로 어울리는 점. */
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
        {/* 화면 언어를 바꾸면 새로 시작한다 — 추천·결과물의 설명은 요청한 때의 언어로 쓰여 한국어 설명이 영어 화면에 남았다(검토 3차) */}
        <RecommendForm key={locale} locale={locale} initialRegions={initial} />
      </div>
    </PageShell>
  );
}
