import type { Metadata } from "next";
import { tx } from "@/components/lab/r-stage/copy";
import { DraftsStage } from "@/components/lab/r-stage/drafts-stage";
import { getLabLocale as getLocale } from "@/lib/locale";
import { getReader, getViewer } from "@/lib/reader-server";

export async function generateMetadata(): Promise<Metadata> {
  const locale = await getLocale();
  return { title: tx(locale, "dr_title") };
}

/* 시장별 초안 — 실행 상태는 브라우저의 r-stage 저장소에 있다(시작 화면에서 넘긴 입력, 새로 고침이면 sessionStorage).
   승인 표지의 이름은 로그인한 사람의 것, 없으면 '검수자' (components/make-flow.tsx 와 같다) */
export default async function DraftsPage() {
  const [locale, viewer, reader] = await Promise.all([getLocale(), getViewer(), getReader()]);
  return <DraftsStage locale={locale} reviewer={viewer ? reader.nick ?? viewer.user : null} />;
}
