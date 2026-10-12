import type { Metadata } from "next";
import { ApprovalQueue } from "@/components/approval-queue";
import { getApprovals, isSampleMode } from "@/lib/data";
import { t } from "@/lib/i18n";
import { getLocale } from "@/lib/locale";
import { getViewer } from "@/lib/reader-server";

export async function generateMetadata(): Promise<Metadata> {
  const locale = await getLocale();
  return { title: `${t(locale, "adm_tab_approvals")} — ${t(locale, "adm_title")} — ${t(locale, "site")}` };
}

/* 관리 '문구 승인'(Plan 20 ⑤) — 초안 화면에서 온 검수 요청(시장 하나가 한 줄)과 지난 기록. 이용자 문구가 있어 검수자·읽기 전용 계정만
   읽는다(proxy·lib/data.getApprovals·백엔드가 각각 확인). 목록을 못 읽으면 예시로 바꾸지 않고 error.tsx 가 '다시 불러오기' 를 낸다. */
export default async function AdminApprovalsPage() {
  const [locale, viewer, list] = await Promise.all([getLocale(), getViewer(), getApprovals()]);
  return (
    <section aria-labelledby="adm-approvals-h" className="space-y-5">
      <h2 id="adm-approvals-h" className="sr-only">{t(locale, "adm_tab_approvals")}</h2>
      <p className="max-w-[760px] text-[15px] leading-[1.55] text-charcoal">{t(locale, "apq_intro")}</p>
      {isSampleMode && <p className="text-[13px] text-steel">{t(locale, "apq_sample")}</p>}
      <ApprovalQueue list={list} locale={locale} live={!isSampleMode} readOnly={!!viewer?.readOnly} />
    </section>
  );
}
