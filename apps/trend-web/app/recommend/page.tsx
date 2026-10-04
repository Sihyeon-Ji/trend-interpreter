import type { Metadata } from "next";
import { PageHeader } from "@/components/page-header";
import { PageShell } from "@/components/page-shell";
import { RecommendForm } from "@/components/recommend-form";
import { getKeywordBoard, getMeta, getTermRecord, isSampleMode } from "@/lib/data";
import { t } from "@/lib/i18n";
import { fmtDateTime } from "@/lib/labels";
import { langTag } from "@/lib/lang";
import { getLocale } from "@/lib/locale";
import { TARGET_REGIONS } from "@/lib/reader";
import { getReader } from "@/lib/reader-server";

// 탭·화면 낭독기가 화면을 가를 수 있게 화면마다 제목을 둔다 — 여러 화면이 사이트 이름 하나뿐이었다(10-04)
export async function generateMetadata(): Promise<Metadata> {
  const locale = await getLocale();
  return { title: `${t(locale, "rec_title")} — ${t(locale, "site")}` };
}

/* 사용 흐름 2단계 '추천받기' (ADR 0001, Plan 07). 사진·문구 → 제품 설명 → 규칙 순위 → 저장된 뜻·국가별 해석으로 어울리는 점.
   주소: ?regions=KR,JP 로 처음 고른 지역(목표 지역만), ?term=<id> 로 사전 항목의 '이 밈으로 만들기' 가 먼저 고른 밈. */
export default async function RecommendPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const [locale, reader, sp] = await Promise.all([getLocale(), getReader(), searchParams]);
  const asked = [sp.regions].flat().filter(Boolean).join(",").split(",").map((s) => s.trim().toUpperCase());
  const fromUrl = TARGET_REGIONS.filter((r) => asked.includes(r));
  // 주소에 지역이 없으면 로그인한 사람의 나라, 익명은 한국 (목표 지역 밖 나라면 한국)
  const initial = fromUrl.length ? fromUrl : reader.region && TARGET_REGIONS.includes(reader.region) ? [reader.region] : ["KR"];
  const termId = [sp.term].flat()[0]?.trim() ?? "";
  const [record, meta] = await Promise.all([
    /^[\w.:-]{1,64}$/.test(termId) ? getTermRecord(termId) : Promise.resolve(null),
    getMeta(),
  ]);
  const pinned = record && record.term.status === "verified" ? { id: record.term.term_id, name: record.term.canonical, lang: langTag(record.term.lang) } : null;
  // 추천 순위는 저장된 사전·대시보드 데이터로 매긴다 — 그 데이터의 시각을 보인다(예시 모드는 예시 보드의 시각)
  const updated = meta?.collected_at ?? meta?.board_generated_at ?? meta?.last_run ?? (isSampleMode ? (await getKeywordBoard(initial)).generated_at : null);
  return (
    <PageShell>
      <div className="space-y-6">
        <PageHeader title={t(locale, "rec_title")} description={t(locale, "rec_intro")}
          meta={updated ? <span className="tabular-nums">{t(locale, "rec_updated").replace("{time}", fmtDateTime(updated, locale))}</span> : undefined} />
        {/* 화면 언어를 바꾸면 새로 시작한다 — 추천·결과물의 설명은 요청한 때의 언어로 쓰여 한국어 설명이 영어 화면에 남았다(검토 3차) */}
        <RecommendForm key={locale} locale={locale} initialRegions={initial} pinned={pinned} sample={isSampleMode} />
      </div>
    </PageShell>
  );
}
