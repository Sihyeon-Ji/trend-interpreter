import type { Metadata } from "next";
import { Archivo } from "next/font/google";
import { Frame } from "@/components/lab/o-report/frame";
import { tr } from "@/lib/lab/o-report/copy";
import { getLabLocale as getLocale } from "@/lib/locale";
import "./o-report.css";

/* 디자인 초안 1 '트렌드 리포트형' (Opus 5.5). 앱의 틀 대신 이 초안이 제 틀을 그린다. 문서: docs/디자인-시안/o-report.md
   숫자에만 Archivo(반쯤 좁은 폭)를 쓴다 — 순위·증감·건수가 리포트의 목소리. 한글·본문은 전역 Pretendard 그대로. */
const numerals = Archivo({ subsets: ["latin"], axes: ["wdth"], variable: "--font-or-num", display: "swap" });

export async function generateMetadata(): Promise<Metadata> {
  const locale = await getLocale();
  const brand = tr(locale, "brand");
  return { title: { default: `${tr(locale, "page_title")} | ${brand}`, template: `%s | ${brand}` } };
}

export default async function OReportLayout({ children }: { children: React.ReactNode }) {
  const locale = await getLocale();
  return (
    <div className={`lab-o-report ${numerals.variable}`}>
      <Frame locale={locale}>{children}</Frame>
    </div>
  );
}
