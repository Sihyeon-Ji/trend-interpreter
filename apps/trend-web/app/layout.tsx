import type { Metadata } from "next";
import { Google_Sans_Flex } from "next/font/google";
import "pretendard/dist/web/variable/pretendardvariable-dynamic-subset.css";
import "./globals.css";
import { Frame } from "@/components/stage/frame";
import { getReviewStats, isSampleMode } from "@/lib/data";
import { getLocale } from "@/lib/locale";
import { getReader, getViewer } from "@/lib/reader-server";

/* 서체: 라틴·숫자는 Google Sans Flex(가변, 광학 크기), 한글은 Pretendard Variable (docs/디자인-시안/r-stage.md) */
const sans = Google_Sans_Flex({ subsets: ["latin"], variable: "--rs-gsf", display: "swap", axes: ["opsz"] });

export const metadata: Metadata = {
  title: "트렌드 통역 · Trend Interpreter",
  description: "나라별로 지금 쓰이는 밈과 조심할 밈, 내 제품에 맞는 밈과 카피 · Memes in use by country, what to avoid, and copy that fits your product",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const locale = await getLocale();
  const [reader, viewer] = await Promise.all([getReader(), getViewer()]);
  // 검수 대기 수는 검수자에게만 — 이용자 화면에 내부 일을 내지 않는다
  const review = viewer?.reviewer ? await getReviewStats().then((s) => s.needs_review).catch(() => null) : null;
  return (
    <html lang={locale} className="h-full antialiased">
      <body className="min-h-full">
        <Frame locale={locale} font={sans.variable} sample={isSampleMode} signedIn={!!viewer} nick={reader.nick ?? null} reviewer={!!viewer?.reviewer} review={review}>{children}</Frame>
      </body>
    </html>
  );
}
