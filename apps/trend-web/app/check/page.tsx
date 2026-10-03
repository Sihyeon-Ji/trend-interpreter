import { CopyCheckForm } from "@/components/copy-check-form";
import { PageHeader } from "@/components/page-header";
import { PageShell } from "@/components/page-shell";
import { StatusBadge } from "@/components/status-badge";
import { isSampleMode } from "@/lib/data";
import { t } from "@/lib/i18n";
import { getLocale } from "@/lib/locale";
import { TARGET_REGIONS } from "@/lib/reader";
import { getReader } from "@/lib/reader-server";

/* 카피 검사 — 마케터가 쓴 문구의 밈을 사전으로 찾아, 고른 시장에서 써도 되는지(규칙)와 뜻에 맞게 썼는지(모델 의견)를 본다.
   시장은 ?regions= 의 첫 목표 지역, 없으면 로그인한 사람의 나라, 그것도 없으면 한국. 문구는 저장하지 않는다. */
export default async function CopyCheckPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const [locale, sp] = await Promise.all([getLocale(), searchParams]);
  const asked = [sp.regions].flat().filter(Boolean).join(",").split(",").map((s) => s.trim().toUpperCase());
  const fromUrl = asked.find((r) => TARGET_REGIONS.includes(r));
  const reader = fromUrl ? {} : await getReader();
  const region = fromUrl ?? (reader.region && TARGET_REGIONS.includes(reader.region) ? reader.region : "KR");
  return (
    <PageShell width="narrow">
      <div className="space-y-6">
        <PageHeader title={t(locale, "check_title")} description={t(locale, "check_intro")}
          meta={isSampleMode ? <StatusBadge tone="muted">{t(locale, "dash_sample_badge")}</StatusBadge> : null} />
        <CopyCheckForm key={locale} locale={locale} initialRegion={region} />
      </div>
    </PageShell>
  );
}
