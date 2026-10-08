import type { Metadata } from "next";
import { Google_Sans_Flex } from "next/font/google";
import { Frame } from "@/components/lab/r-stage/frame";
import { getReviewStats } from "@/lib/data";
import { getLocale } from "@/lib/locale";
import { getReader, getViewer } from "@/lib/reader-server";
import "./r-stage.css";

/* 시안 r-stage '무대' — 앱의 틀 대신 이 시안이 제 틀을 그린다. 문서: docs/디자인-시안/r-stage.md
   서체: 라틴·숫자는 Google Sans Flex(가변, 광학 크기), 한글은 앱이 이미 싣는 Pretendard Variable. */
const sans = Google_Sans_Flex({ subsets: ["latin"], variable: "--rs-gsf", display: "swap", axes: ["opsz"] });

export const metadata: Metadata = { title: { default: "Trend Interpreter", template: "%s · Trend Interpreter" } };

export default async function RStageLayout({ children }: { children: React.ReactNode }) {
  const [locale, viewer, reader] = await Promise.all([getLocale(), getViewer(), getReader()]);
  // 검수 대기 수는 검수자에게만 — 이용자 화면에 내부 일을 내지 않는다
  const review = viewer?.reviewer ? await getReviewStats().then((s) => s.needs_review).catch(() => null) : null;
  const who = viewer ? reader.nick ?? viewer.user : null;
  return (
    <div className={`r-stage ${sans.variable}`} data-locale={locale}>
      <Frame locale={locale} who={who} review={review}>{children}</Frame>
    </div>
  );
}
