import type { Metadata } from "next";
import { tx } from "@/components/stage/copy";
import { DraftsStage } from "@/components/stage/drafts-stage";
import { t } from "@/lib/i18n";
import { getLocale } from "@/lib/locale";
import { getReader, getViewer } from "@/lib/reader-server";

export async function generateMetadata(): Promise<Metadata> {
  const locale = await getLocale();
  return { title: `${tx(locale, "dr_title")} — ${t(locale, "site")}` };
}

/* 시장별 초안 — 실행 상태는 브라우저의 만들기 저장소(components/stage/store.ts)에 있다(시작 화면에서 넘긴 입력, 새로 고침이면 sessionStorage).
   승인 표지의 이름은 로그인한 사람의 것, 없으면 '검수자'  */
export default async function DraftsPage() {
  const [locale, viewer, reader] = await Promise.all([getLocale(), getViewer(), getReader()]);
  return (
    <main id="main" className="rs-main" tabIndex={-1}>
      <DraftsStage locale={locale} reviewer={viewer ? reader.nick ?? viewer.user : null} />
    </main>
  );
}
