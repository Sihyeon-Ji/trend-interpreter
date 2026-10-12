import type { Metadata } from "next";
import { tx } from "@/components/stage/copy";
import { DraftsStage } from "@/components/stage/drafts-stage";
import { t } from "@/lib/i18n";
import { getLocale } from "@/lib/locale";
import { getViewer } from "@/lib/reader-server";

export async function generateMetadata(): Promise<Metadata> {
  const locale = await getLocale();
  return { title: `${tx(locale, "dr_title")} — ${t(locale, "site")}` };
}

/* 시장별 초안 — 실행 상태는 브라우저의 만들기 저장소(components/stage/store.ts)에 있다(시작 화면에서 넘긴 입력, 새로 고침이면 sessionStorage).
   승인은 검수자만, 검수 요청은 로그인한 계정만 — 서버(app/api/approvals)가 세션으로 다시 보고, 이름도 세션에서 적는다. 여기서는 단추만 고른다 */
export default async function DraftsPage() {
  const [locale, viewer] = await Promise.all([getLocale(), getViewer()]);
  return (
    <main id="main" className="rs-main" tabIndex={-1}>
      <DraftsStage locale={locale} viewer={viewer ? { reviewer: viewer.reviewer, readOnly: viewer.readOnly } : null} />
    </main>
  );
}
